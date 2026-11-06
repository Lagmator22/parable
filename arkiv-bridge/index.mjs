// Tiny local HTTP service that lets the Python engine use the official Arkiv JS SDK.
// It signs with ARKIV_PRIVATE_KEY (repo-root .env), writes entities to the Rabdi testnet and queries them.
// Listens on 127.0.0.1 only, so nothing outside this computer can make it spend our testnet funds.
import http from "node:http";
import { timingSafeEqual } from "node:crypto";
import { createPublicClient, createWalletClient, ExpirationTime } from "@arkiv-network/sdk";
import { rabdi } from "@arkiv-network/sdk/chains";
import { and, eq } from "@arkiv-network/sdk/query";
import { addr, bytes, defineSchema, i32, str, u256, u64 } from "@arkiv-network/sdk/schema";
import { hexToString, http as httpTransport, stringToBytes } from "viem";
import { privateKeyToAccount } from "viem/accounts";

for (const file of ["../.env", "../.env.arkiv-spike"]) { // repo-root .env, then the throwaway spike key
  try { process.loadEnvFile(new URL(file, import.meta.url)); } catch { /* file not there, fine */ }
}
const PORT = Number(process.env.ARKIV_BRIDGE_PORT ?? 8787);
// SECURITY: every request must carry this shared password, so a website open in your browser can't use the bridge.
const TOKEN = process.env.ARKIV_BRIDGE_TOKEN ?? "";
if (TOKEN.length < 16) throw new Error("ARKIV_BRIDGE_TOKEN must be set in .env (16+ random characters)");
const rawKey = process.env.ARKIV_PRIVATE_KEY ?? "";
if (!rawKey) throw new Error("ARKIV_PRIVATE_KEY is not set");
const account = privateKeyToAccount(rawKey.startsWith("0x") ? rawKey : `0x${rawKey}`);
const chain = rabdi({ accessKey: process.env.ARKIV_ACCESS_KEY ?? "" });
const reader = createPublicClient({ chain, transport: httpTransport() });
const writer = createWalletClient({ chain, transport: httpTransport(), account });

// Attributes arrive as {name: [type, value]}, e.g. {"bot_id": ["u256", "7"], "status": ["str", "alive"]}.
const TYPES = { str, u256, u64, i32, addr };
const toValue = ([type, v]) => TYPES[type](type === "str" || type === "addr" ? v : BigInt(v));
const column = ([type]) => TYPES[type]().indexed();

// A schema is the list of columns (name + type). `body` is the full JSON record, stored but not indexed.
function makeSchema(name, attributes) {
  const columns = Object.fromEntries(Object.entries(attributes).map(([k, a]) => [k, column(a)]));
  return defineSchema(name, { ...columns, body: bytes() });
}
const valuesOf = (attributes, body) =>
  ({ ...Object.fromEntries(Object.entries(attributes).map(([k, a]) => [k, toValue(a)])), body: stringToBytes(body ?? "{}") });

async function createEntity({ schema, attributes, expiresInSeconds, body, readonly }) {
  const flags = readonly ? { readonly: true, permissionlessExtension: true } : { permissionlessExtension: true };
  const r = await writer.createEntity(makeSchema(schema, attributes), valuesOf(attributes, body),
    { expiration: ExpirationTime.fromSeconds(expiresInSeconds), flags });
  return { key: r.entityKey, txHash: r.txHash };
}

// Change some attributes of an entity we own, and optionally push its expiry out (used when a bot dies).
async function patchEntity({ schema, key, attributes, body, extendSeconds }) {
  const set = valuesOf(attributes, body);
  const patch = await writer.patchEntity(makeSchema(schema, attributes), key, { set });
  if (extendSeconds) {
    try {
      await writer.extendEntity({ entityKey: key, expiration: ExpirationTime.fromSeconds(extendSeconds) });
    } catch (err) {
      // Rebuilt dead bots already have a 180-day expiry; Arkiv rejects extending to a slightly shorter block.
      if (!String(err.shortMessage ?? err.message).includes("shorten its life")) throw err;
    }
  }
  return { key, txHash: patch.txHash };
}

// SECURITY: anyone can write entities on Arkiv, so we only read entities owned by our writer wallet.
async function query({ schema, where = {}, owner }) {
  const filters = [eq("arkiv.schema", schema), ...Object.entries(where).map(([k, a]) => eq(k, toValue(a)))];
  const rows = [];
  for (let offset = 0; ; offset += 100) {
    const page = await reader.select({ $key: true, $expiresAt: true, $attributes: true })
      .where(and(...filters)).ownedBy(owner ?? account.address).limit(100).offset(offset).fetch();
    rows.push(...page.entities);
    if (page.entities.length < 100) break;
  }
  return rows.map((row) => {
    const { body, ...rest } = row.$attributes ?? {};
    const attributes = Object.fromEntries(Object.entries(rest).map(([k, v]) => [k, String(v.value)]));
    return { key: row.$key, attributes, body: body ? hexToString(body.value) : null, expiresAt: String(row.$expiresAt) };
  });
}

const routes = {
  "GET /health": async () => ({ writer: account.address, chainId: chain.id }),
  "POST /entities": createEntity,
  "POST /patch": patchEntity,
  "POST /query": query,
};

// Only our own Python engine may call us: right password, local Host, no browser Origin, JSON body.
function allowed(req) {
  const given = Buffer.from(req.headers["x-bridge-token"] ?? "");
  const want = Buffer.from(TOKEN);
  const goodToken = given.length === want.length && timingSafeEqual(given, want);
  const goodHost = [`127.0.0.1:${PORT}`, `localhost:${PORT}`].includes(req.headers.host);
  const isJson = req.method === "GET" || (req.headers["content-type"] ?? "").startsWith("application/json");
  return goodToken && goodHost && !req.headers.origin && isJson;
}

http.createServer(async (req, res) => {
  let body = "";
  for await (const chunk of req) body += chunk;
  const handler = routes[`${req.method} ${req.url}`];
  try {
    if (!allowed(req)) throw Object.assign(new Error("forbidden"), { status: 403 });
    if (!handler) throw Object.assign(new Error("not found"), { status: 404 });
    const out = await handler(body ? JSON.parse(body) : {});
    res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(out));
  } catch (err) {
    res.writeHead(err.status ?? 500, { "content-type": "application/json" }).end(JSON.stringify({ error: String(err.shortMessage ?? err.message) }));
  }
}).listen(PORT, "127.0.0.1", () => console.log(`arkiv-bridge on 127.0.0.1:${PORT}, writer ${account.address}`));

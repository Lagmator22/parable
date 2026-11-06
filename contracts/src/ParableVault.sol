// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AggregatorV3Interface} from "./interfaces/AggregatorV3Interface.sol";
import {IBadgeOracle} from "./interfaces/IBadgeOracle.sol";

/// Parable kernel. Holds each bot's (practice) money, checks its ENS badge on every trade,
/// executes trades at the Chainlink price, and measures loss itself. Bots only *ask*.
/// Units: USD 6 decimals, ETH 18 decimals, Chainlink price 8 decimals.
contract ParableVault {
    enum Status { None, Alive, Dead }
    enum DeathCause { None, Expired, Killed, LossLimit }

    struct Bot {
        address bot;
        address creatorWallet;
        bytes32 creatorId;
        bytes32 badgeNode;
        bytes32 strategyId;
        uint64 expiresAt;
        uint64 bornAt;
        uint64 diedAt;
        uint16 maxLossBps;
        Status status;
        DeathCause cause;
        uint256 startCashUsd;
        uint256 maxTradeUsd;
        uint256 cashUsd; // 6 decimals
        uint256 ethWei; // 18 decimals
        uint256 hwmUsd; // high-water mark of equity, 6 decimals
        uint256 finalEquityUsd; // set on death
    }

    // ethWei = usd6 * ETH_PER_USD_NUM / price8   (1e18 * 1e8 / 1e6)
    uint256 private constant ETH_PER_USD_NUM = 1e20;

    AggregatorV3Interface public immutable priceFeed;
    IBadgeOracle public immutable badgeOracle;
    address public immutable operator;
    uint256 public immutable maxPriceAge;

    mapping(uint256 => Bot) private _bots;
    mapping(address => uint256) public botIdOf;
    mapping(bytes32 => address) public walletOfCreator;
    mapping(address => bytes32) public creatorOfWallet;
    mapping(bytes32 => uint256) public creatorBorn;
    mapping(bytes32 => uint256) public creatorDead;
    uint256 public totalBorn;
    uint256 public totalDead;
    uint256 public nextBotId = 1;

    event BotBorn(
        uint256 indexed botId,
        address indexed bot,
        bytes32 indexed creatorId,
        bytes32 strategyId,
        bytes32 badgeNode,
        uint64 expiresAt,
        uint256 startCashUsd,
        uint256 maxTradeUsd,
        uint16 maxLossBps
    );
    event Traded(
        uint256 indexed botId, bool buyEth, uint256 amountUsd, uint256 ethAmount, uint256 priceUsd8, uint256 equityUsd
    );
    event BotDied(
        uint256 indexed botId,
        DeathCause cause,
        uint256 finalEquityUsd,
        uint256 startCashUsd,
        uint64 bornAt,
        uint64 diedAt
    );
    event BadgeRevokeFailed(uint256 indexed botId, bytes32 badgeNode);

    error NotOperator();
    error NotRegistered();
    error NotAlive();
    error Expired();
    error NotExpired();
    error BadgeInvalid();
    error OverTradeLimit();
    error InsufficientBalance();
    error StalePrice();
    error NotBot();
    error NotOverLimit();
    error CreatorIdentityMismatch();
    error Unauthorized();
    error BotAlreadyRegistered();
    error InvalidParams();
    error ZeroAmount();

    constructor(address priceFeed_, address badgeOracle_, address operator_, uint256 maxPriceAge_) {
        if (priceFeed_ == address(0) || badgeOracle_ == address(0) || operator_ == address(0)) revert InvalidParams();
        priceFeed = AggregatorV3Interface(priceFeed_);
        badgeOracle = IBadgeOracle(badgeOracle_);
        operator = operator_;
        maxPriceAge = maxPriceAge_;
    }

    // ---------------------------------------------------------------- registration

    function registerBot(
        address bot,
        bytes32 creatorId,
        address creatorWallet,
        bytes32 badgeNode,
        uint64 expiresAt,
        uint256 startCashUsd,
        uint256 maxTradeUsd,
        uint16 maxLossBps,
        bytes32 strategyId
    ) external returns (uint256 botId) {
        if (msg.sender != operator) revert NotOperator();
        if (
            bot == address(0) || creatorWallet == address(0) || creatorId == bytes32(0) || startCashUsd == 0
                || maxLossBps == 0 || maxLossBps > 10_000 || expiresAt <= block.timestamp
        ) revert InvalidParams();
        if (botIdOf[bot] != 0) revert BotAlreadyRegistered();

        // One creatorId <-> one creatorWallet, both directions.
        address boundWallet = walletOfCreator[creatorId];
        bytes32 boundCreator = creatorOfWallet[creatorWallet];
        if (boundWallet == address(0) && boundCreator == bytes32(0)) {
            walletOfCreator[creatorId] = creatorWallet;
            creatorOfWallet[creatorWallet] = creatorId;
        } else if (boundWallet != creatorWallet || boundCreator != creatorId) {
            revert CreatorIdentityMismatch();
        }

        botId = nextBotId++;
        Bot storage b = _bots[botId];
        b.bot = bot;
        b.creatorWallet = creatorWallet;
        b.creatorId = creatorId;
        b.badgeNode = badgeNode;
        b.strategyId = strategyId;
        b.expiresAt = expiresAt;
        b.bornAt = uint64(block.timestamp);
        b.maxLossBps = maxLossBps;
        b.status = Status.Alive;
        b.startCashUsd = startCashUsd;
        b.maxTradeUsd = maxTradeUsd;
        b.cashUsd = startCashUsd;
        b.hwmUsd = startCashUsd;

        botIdOf[bot] = botId;
        totalBorn++;
        creatorBorn[creatorId]++;

        emit BotBorn(botId, bot, creatorId, strategyId, badgeNode, expiresAt, startCashUsd, maxTradeUsd, maxLossBps);
    }

    // ---------------------------------------------------------------- trading

    function trade(uint256 botId, bool buyEth, uint256 amountUsd) external {
        Bot storage b = _bots[botId];
        if (b.status == Status.None) revert NotRegistered();
        if (msg.sender != b.bot) revert NotBot();
        if (b.status != Status.Alive) revert NotAlive();
        if (block.timestamp >= b.expiresAt) revert Expired();
        if (!badgeOracle.isValid(b.badgeNode, b.bot)) revert BadgeInvalid();
        if (amountUsd == 0) revert ZeroAmount();
        if (amountUsd > b.maxTradeUsd) revert OverTradeLimit();

        uint256 price = _price();
        uint256 ethAmount;
        if (buyEth) {
            if (amountUsd > b.cashUsd) revert InsufficientBalance();
            ethAmount = (amountUsd * ETH_PER_USD_NUM) / price; // round down: bot gets slightly less
            b.cashUsd -= amountUsd;
            b.ethWei += ethAmount;
        } else {
            ethAmount = _ceilDiv(amountUsd * ETH_PER_USD_NUM, price); // round up: bot gives slightly more
            if (ethAmount > b.ethWei) revert InsufficientBalance();
            b.ethWei -= ethAmount;
            b.cashUsd += amountUsd;
        }

        uint256 equity = _equity(b, price);
        if (equity > b.hwmUsd) b.hwmUsd = equity;
        emit Traded(botId, buyEth, amountUsd, ethAmount, price, equity);

        if (_overLimit(b, equity)) _die(botId, b, DeathCause.LossLimit, equity);
    }

    // ---------------------------------------------------------------- death

    /// Anyone may call. Kills the bot if its drawdown from the high-water mark is at or past its limit.
    function checkAndRevoke(uint256 botId) external {
        Bot storage b = _bots[botId];
        if (b.status == Status.None) revert NotRegistered();
        if (b.status != Status.Alive) revert NotAlive();
        uint256 equity = _equity(b, _price());
        if (!_overLimit(b, equity)) revert NotOverLimit();
        _die(botId, b, DeathCause.LossLimit, equity);
    }

    /// Creator wallet or operator.
    function kill(uint256 botId) external {
        Bot storage b = _bots[botId];
        if (b.status == Status.None) revert NotRegistered();
        if (msg.sender != b.creatorWallet && msg.sender != operator) revert Unauthorized();
        if (b.status != Status.Alive) revert NotAlive();
        // Death must not depend on the price feed (see _equitySafe).
        _die(botId, b, DeathCause.Killed, _equitySafe(b));
    }

    /// Anyone, once the lease is over.
    function expire(uint256 botId) external {
        Bot storage b = _bots[botId];
        if (b.status == Status.None) revert NotRegistered();
        if (b.status != Status.Alive) revert NotAlive();
        if (block.timestamp < b.expiresAt) revert NotExpired();
        _die(botId, b, DeathCause.Expired, _equitySafe(b));
    }

    function _die(uint256 botId, Bot storage b, DeathCause cause, uint256 finalEquity) private {
        b.status = Status.Dead;
        b.cause = cause;
        b.diedAt = uint64(block.timestamp);
        b.finalEquityUsd = finalEquity;
        totalDead++;
        creatorDead[b.creatorId]++;

        // A broken or hostile badge oracle must never keep a bot alive.
        try badgeOracle.revoke(b.badgeNode) {} catch {
            emit BadgeRevokeFailed(botId, b.badgeNode);
        }

        emit BotDied(botId, cause, finalEquity, b.startCashUsd, b.bornAt, b.diedAt);
    }

    // ---------------------------------------------------------------- views

    function equityUsd(uint256 botId) external view returns (uint256) {
        Bot storage b = _bots[botId];
        if (b.status == Status.None) revert NotRegistered();
        if (b.status == Status.Dead) return b.finalEquityUsd;
        return _equity(b, _price());
    }

    function getBot(uint256 botId) external view returns (Bot memory) {
        return _bots[botId];
    }

    // ---------------------------------------------------------------- internals

    function _price() private view returns (uint256) {
        (, int256 answer,, uint256 updatedAt,) = priceFeed.latestRoundData();
        if (answer <= 0) revert StalePrice();
        if (updatedAt == 0 || updatedAt > block.timestamp || block.timestamp - updatedAt > maxPriceAge) {
            revert StalePrice();
        }
        return uint256(answer);
    }

    function _equity(Bot storage b, uint256 price) private view returns (uint256) {
        return b.cashUsd + (b.ethWei * price) / ETH_PER_USD_NUM;
    }

    /// Equity for kill/expire: live price when fresh. If the feed is stale or broken, falls back to
    /// cash only (ETH valued at zero) so death is never blocked; the recorded final equity is then
    /// a conservative undercount.
    function _equitySafe(Bot storage b) private view returns (uint256) {
        try this.priceView() returns (uint256 price) {
            return _equity(b, price);
        } catch {
            return b.cashUsd;
        }
    }

    /// External wrapper so `_equitySafe` can try/catch the internal price check.
    function priceView() external view returns (uint256) {
        return _price();
    }

    function _overLimit(Bot storage b, uint256 equity) private view returns (bool) {
        if (equity >= b.hwmUsd) return false;
        return ((b.hwmUsd - equity) * 10_000) / b.hwmUsd >= b.maxLossBps;
    }

    function _ceilDiv(uint256 a, uint256 d) private pure returns (uint256) {
        return a == 0 ? 0 : (a - 1) / d + 1;
    }
}

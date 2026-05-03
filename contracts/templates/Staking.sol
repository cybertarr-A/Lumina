// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

/// @title {{ contract_name }}
/// @notice Staking contract with configurable rewards and lock periods
/// @dev Reward rate: {{ reward_rate }} tokens/second | Lock: {{ lock_period }} seconds
contract {{ contract_name }} is Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    // ── Errors ─────────────────────────────────────────────────────────────
    error ZeroAmount();
    error ZeroAddress();
    error StillLocked(uint256 unlockTime);
    error NothingToWithdraw();
    error InsufficientRewardBalance();

    // ── Events ─────────────────────────────────────────────────────────────
    event Staked(address indexed user, uint256 amount);
    event Unstaked(address indexed user, uint256 amount);
    event RewardClaimed(address indexed user, uint256 reward);
    event RewardRateUpdated(uint256 oldRate, uint256 newRate);
    event EmergencyWithdraw(address indexed user, uint256 amount);

    // ── State ──────────────────────────────────────────────────────────────
    IERC20 public immutable stakingToken;
    IERC20 public immutable rewardToken;

    uint256 public rewardRate;       // reward tokens per second
    uint256 public lockPeriod;       // seconds tokens are locked after staking
    uint256 public totalStaked;

    struct StakeInfo {
        uint256 amount;
        uint256 rewardDebt;
        uint256 stakedAt;
        uint256 lastRewardTime;
    }

    mapping(address => StakeInfo) public stakes;

    // ── Constructor ────────────────────────────────────────────────────────
    constructor(
        address initialOwner,
        address _stakingToken,
        address _rewardToken,
        uint256 _rewardRate,
        uint256 _lockPeriod
    ) Ownable(initialOwner) {
        if (_stakingToken == address(0) || _rewardToken == address(0)) revert ZeroAddress();
        stakingToken = IERC20(_stakingToken);
        rewardToken = IERC20(_rewardToken);
        rewardRate = _rewardRate;
        lockPeriod = _lockPeriod;
    }

    // ── Core Functions ─────────────────────────────────────────────────────

    /// @notice Stake tokens to earn rewards
    function stake(uint256 amount) external nonReentrant whenNotPaused {
        if (amount == 0) revert ZeroAmount();
        StakeInfo storage info = stakes[msg.sender];

        // Claim pending rewards first
        if (info.amount > 0) _claimReward(msg.sender);

        stakingToken.safeTransferFrom(msg.sender, address(this), amount);
        info.amount += amount;
        info.stakedAt = block.timestamp;
        info.lastRewardTime = block.timestamp;
        totalStaked += amount;

        emit Staked(msg.sender, amount);
    }

    /// @notice Unstake tokens after lock period
    function unstake(uint256 amount) external nonReentrant {
        StakeInfo storage info = stakes[msg.sender];
        if (amount == 0) revert ZeroAmount();
        if (info.amount < amount) revert NothingToWithdraw();
        if (block.timestamp < info.stakedAt + lockPeriod)
            revert StillLocked(info.stakedAt + lockPeriod);

        _claimReward(msg.sender);
        info.amount -= amount;
        totalStaked -= amount;
        stakingToken.safeTransfer(msg.sender, amount);

        emit Unstaked(msg.sender, amount);
    }

    /// @notice Claim accumulated rewards without unstaking
    function claimReward() external nonReentrant {
        if (stakes[msg.sender].amount == 0) revert NothingToWithdraw();
        _claimReward(msg.sender);
    }

    /// @notice Emergency unstake — forfeits unclaimed rewards
    function emergencyWithdraw() external nonReentrant {
        StakeInfo storage info = stakes[msg.sender];
        uint256 amount = info.amount;
        if (amount == 0) revert NothingToWithdraw();
        info.amount = 0;
        info.rewardDebt = 0;
        totalStaked -= amount;
        stakingToken.safeTransfer(msg.sender, amount);
        emit EmergencyWithdraw(msg.sender, amount);
    }

    // ── View Functions ─────────────────────────────────────────────────────

    /// @notice Calculate pending rewards for a user
    function pendingReward(address user) public view returns (uint256) {
        StakeInfo storage info = stakes[user];
        if (info.amount == 0) return 0;
        uint256 elapsed = block.timestamp - info.lastRewardTime;
        return (info.amount * rewardRate * elapsed) / 1e18;
    }

    // ── Admin ──────────────────────────────────────────────────────────────

    function setRewardRate(uint256 newRate) external onlyOwner {
        emit RewardRateUpdated(rewardRate, newRate);
        rewardRate = newRate;
    }

    function setLockPeriod(uint256 newPeriod) external onlyOwner { lockPeriod = newPeriod; }
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function fundRewards(uint256 amount) external onlyOwner {
        rewardToken.safeTransferFrom(msg.sender, address(this), amount);
    }

    // ── Internal ───────────────────────────────────────────────────────────

    function _claimReward(address user) internal {
        uint256 reward = pendingReward(user);
        if (reward > 0) {
            uint256 available = rewardToken.balanceOf(address(this));
            if (reward > available) reward = available;
            stakes[user].rewardDebt += reward;
            stakes[user].lastRewardTime = block.timestamp;
            rewardToken.safeTransfer(user, reward);
            emit RewardClaimed(user, reward);
        }
    }
}

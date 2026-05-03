// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
{% if burnable %}
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
{% endif %}
{% if pausable %}
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Pausable.sol";
{% endif %}
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title {{ contract_name }}
/// @author Smart Contract Generator Platform
/// @notice ERC-20 token with configurable features
/// @dev Generated from template — review before production deployment
contract {{ contract_name }} is ERC20{% if burnable %}, ERC20Burnable{% endif %}{% if pausable %}, ERC20Pausable{% endif %}, Ownable {

    // ── Errors ─────────────────────────────────────────────────────────────
    error ZeroAddress();
    error ZeroAmount();
    error ExceedsMaxSupply(uint256 requested, uint256 available);

    // ── Events ─────────────────────────────────────────────────────────────
    event Minted(address indexed to, uint256 amount);
    event MaxSupplyUpdated(uint256 oldMax, uint256 newMax);

    // ── State ──────────────────────────────────────────────────────────────
    {% if mintable %}
    uint256 public maxSupply;
    {% endif %}

    // ── Constructor ────────────────────────────────────────────────────────
    constructor(
        address initialOwner,
        uint256 initialSupply{% if mintable %},
        uint256 _maxSupply{% endif %}
    )
        ERC20("{{ token_name }}", "{{ token_symbol }}")
        Ownable(initialOwner)
    {
        if (initialOwner == address(0)) revert ZeroAddress();
        {% if mintable %}
        require(_maxSupply >= initialSupply, "Max supply must be >= initial supply");
        maxSupply = _maxSupply * 10 ** decimals();
        {% endif %}
        _mint(initialOwner, initialSupply * 10 ** decimals());
    }

    {% if mintable %}
    // ── Minting ────────────────────────────────────────────────────────────

    /// @notice Mint new tokens to a recipient
    /// @param to Recipient address
    /// @param amount Amount of tokens to mint (in base units)
    function mint(address to, uint256 amount) external onlyOwner {
        if (to == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();
        if (totalSupply() + amount > maxSupply)
            revert ExceedsMaxSupply(amount, maxSupply - totalSupply());
        _mint(to, amount);
        emit Minted(to, amount);
    }

    /// @notice Update the maximum supply cap
    /// @param newMax New maximum supply (in base units)
    function setMaxSupply(uint256 newMax) external onlyOwner {
        require(newMax >= totalSupply(), "Cannot set max below current supply");
        uint256 old = maxSupply;
        maxSupply = newMax;
        emit MaxSupplyUpdated(old, newMax);
    }
    {% endif %}

    {% if pausable %}
    // ── Pause controls ─────────────────────────────────────────────────────

    /// @notice Pause all token transfers
    function pause() external onlyOwner { _pause(); }

    /// @notice Resume all token transfers
    function unpause() external onlyOwner { _unpause(); }
    {% endif %}

    // ── Overrides ──────────────────────────────────────────────────────────
    {% if pausable %}
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Pausable)
    {
        super._update(from, to, value);
    }
    {% endif %}
}

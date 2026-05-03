// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721Pausable.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/interfaces/IERC2981.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

/// @title {{ contract_name }}
/// @author Smart Contract Generator Platform
/// @notice ERC-721 NFT collection with royalties (EIP-2981)
/// @dev Max supply: {{ max_supply }} | Mint price: {{ mint_price_wei }} wei
contract {{ contract_name }} is ERC721, ERC721URIStorage, ERC721Pausable, Ownable, IERC2981 {
    using Counters for Counters.Counter;

    // ── Errors ─────────────────────────────────────────────────────────────
    error MaxSupplyReached();
    error InsufficientPayment(uint256 sent, uint256 required);
    error TokenDoesNotExist(uint256 tokenId);
    error ZeroAddress();
    error InvalidRoyalty();

    // ── Events ─────────────────────────────────────────────────────────────
    event NFTMinted(address indexed to, uint256 indexed tokenId, string uri);
    event RoyaltyUpdated(address receiver, uint96 feeBps);
    event Withdrawn(address indexed to, uint256 amount);

    // ── State ──────────────────────────────────────────────────────────────
    Counters.Counter private _tokenIds;

    uint256 public immutable maxSupply;
    uint256 public mintPrice;

    address private _royaltyReceiver;
    uint96 private _royaltyFeeBps; // basis points (e.g., 250 = 2.5%)

    // ── Constructor ────────────────────────────────────────────────────────
    constructor(
        address initialOwner,
        uint256 _maxSupply,
        uint256 _mintPrice,
        uint96 _royaltyBps
    )
        ERC721("{{ token_name }}", "{{ token_symbol }}")
        Ownable(initialOwner)
    {
        if (initialOwner == address(0)) revert ZeroAddress();
        if (_royaltyBps > 10_000) revert InvalidRoyalty();
        maxSupply = _maxSupply;
        mintPrice = _mintPrice;
        _royaltyReceiver = initialOwner;
        _royaltyFeeBps = _royaltyBps;
    }

    // ── Minting ────────────────────────────────────────────────────────────

    /// @notice Mint a new NFT
    /// @param to Recipient address
    /// @param uri Token metadata URI (IPFS CID recommended)
    function safeMint(address to, string calldata uri) external payable whenNotPaused {
        if (to == address(0)) revert ZeroAddress();
        if (_tokenIds.current() >= maxSupply) revert MaxSupplyReached();
        if (msg.value < mintPrice) revert InsufficientPayment(msg.value, mintPrice);

        uint256 tokenId = _tokenIds.current();
        _tokenIds.increment();
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);

        emit NFTMinted(to, tokenId, uri);
    }

    /// @notice Owner mint (no payment required)
    function ownerMint(address to, string calldata uri) external onlyOwner {
        if (_tokenIds.current() >= maxSupply) revert MaxSupplyReached();
        uint256 tokenId = _tokenIds.current();
        _tokenIds.increment();
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);
        emit NFTMinted(to, tokenId, uri);
    }

    // ── Royalties (EIP-2981) ───────────────────────────────────────────────

    /// @inheritdoc IERC2981
    function royaltyInfo(uint256, uint256 salePrice)
        external view override returns (address receiver, uint256 royaltyAmount)
    {
        receiver = _royaltyReceiver;
        royaltyAmount = (salePrice * _royaltyFeeBps) / 10_000;
    }

    /// @notice Update royalty configuration
    function setRoyalty(address receiver, uint96 feeBps) external onlyOwner {
        if (receiver == address(0)) revert ZeroAddress();
        if (feeBps > 10_000) revert InvalidRoyalty();
        _royaltyReceiver = receiver;
        _royaltyFeeBps = feeBps;
        emit RoyaltyUpdated(receiver, feeBps);
    }

    // ── Admin ──────────────────────────────────────────────────────────────

    function setMintPrice(uint256 newPrice) external onlyOwner { mintPrice = newPrice; }
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    /// @notice Withdraw contract ETH balance
    function withdraw() external onlyOwner {
        uint256 balance = address(this).balance;
        (bool ok, ) = owner().call{value: balance}("");
        require(ok, "Withdrawal failed");
        emit Withdrawn(owner(), balance);
    }

    // ── View ───────────────────────────────────────────────────────────────

    function totalMinted() external view returns (uint256) { return _tokenIds.current(); }
    function totalSupply() external view returns (uint256) { return _tokenIds.current(); }

    // ── Overrides ──────────────────────────────────────────────────────────

    function tokenURI(uint256 tokenId)
        public view override(ERC721, ERC721URIStorage) returns (string memory)
    { return super.tokenURI(tokenId); }

    function supportsInterface(bytes4 interfaceId)
        public view override(ERC721, ERC721URIStorage, IERC165) returns (bool)
    { return interfaceId == type(IERC2981).interfaceId || super.supportsInterface(interfaceId); }

    function _update(address to, uint256 tokenId, address auth)
        internal override(ERC721, ERC721Pausable) returns (address)
    { return super._update(to, tokenId, auth); }
}

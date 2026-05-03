// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Burnable.sol";
import "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Pausable.sol";
import "@openzeppelin/contracts/token/ERC1155/extensions/ERC1155Supply.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title {{ contract_name }}
/// @notice ERC-1155 multi-token standard with batch minting
contract {{ contract_name }} is ERC1155, ERC1155Burnable, ERC1155Pausable, ERC1155Supply, Ownable {

    error ZeroAddress();
    error ArrayLengthMismatch();

    event BatchMinted(address indexed to, uint256[] ids, uint256[] amounts);
    event URIUpdated(string newUri);

    mapping(uint256 => string) private _tokenURIs;

    constructor(address initialOwner, string memory baseUri)
        ERC1155(baseUri)
        Ownable(initialOwner)
    {
        if (initialOwner == address(0)) revert ZeroAddress();
    }

    /// @notice Mint a single token type
    function mint(address to, uint256 id, uint256 amount, bytes memory data)
        external onlyOwner
    {
        _mint(to, id, amount, data);
    }

    /// @notice Batch mint multiple token types
    function mintBatch(address to, uint256[] memory ids, uint256[] memory amounts, bytes memory data)
        external onlyOwner
    {
        if (ids.length != amounts.length) revert ArrayLengthMismatch();
        _mintBatch(to, ids, amounts, data);
        emit BatchMinted(to, ids, amounts);
    }

    /// @notice Set URI for a specific token ID
    function setTokenURI(uint256 id, string memory tokenUri) external onlyOwner {
        _tokenURIs[id] = tokenUri;
    }

    /// @notice Update base URI
    function setURI(string memory newuri) external onlyOwner {
        _setURI(newuri);
        emit URIUpdated(newuri);
    }

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function uri(uint256 id) public view override returns (string memory) {
        string memory tokenUri = _tokenURIs[id];
        if (bytes(tokenUri).length > 0) return tokenUri;
        return super.uri(id);
    }

    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal override(ERC1155, ERC1155Pausable, ERC1155Supply)
    { super._update(from, to, ids, values); }
}

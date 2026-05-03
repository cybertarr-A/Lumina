const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ERC20 Token", function () {
  let token, owner, addr1, addr2;

  beforeEach(async function () {
    [owner, addr1, addr2] = await ethers.getSigners();
    const Token = await ethers.getContractFactory("TestERC20");
    token = await Token.deploy(owner.address, 1_000_000, 10_000_000);
    await token.waitForDeployment();
  });

  describe("Deployment", function () {
    it("should assign initial supply to owner", async function () {
      const balance = await token.balanceOf(owner.address);
      expect(balance).to.equal(ethers.parseEther("1000000"));
    });

    it("should set correct name and symbol", async function () {
      expect(await token.name()).to.equal("TestERC20");
      expect(await token.symbol()).to.equal("SCG");
    });

    it("should set max supply correctly", async function () {
      expect(await token.maxSupply()).to.equal(ethers.parseEther("10000000"));
    });
  });

  describe("Minting", function () {
    it("should allow owner to mint tokens", async function () {
      await token.mint(addr1.address, ethers.parseEther("500"));
      expect(await token.balanceOf(addr1.address)).to.equal(ethers.parseEther("500"));
    });

    it("should revert minting from non-owner", async function () {
      await expect(
        token.connect(addr1).mint(addr2.address, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(token, "OwnableUnauthorizedAccount");
    });

    it("should revert minting zero amount", async function () {
      await expect(token.mint(addr1.address, 0)).to.be.revertedWithCustomError(
        token, "ZeroAmount"
      );
    });

    it("should revert minting to zero address", async function () {
      await expect(
        token.mint(ethers.ZeroAddress, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(token, "ZeroAddress");
    });

    it("should revert minting beyond max supply", async function () {
      await expect(
        token.mint(addr1.address, ethers.parseEther("9999999"))
      ).to.be.revertedWithCustomError(token, "ExceedsMaxSupply");
    });

    it("should emit Minted event", async function () {
      await expect(token.mint(addr1.address, ethers.parseEther("100")))
        .to.emit(token, "Minted")
        .withArgs(addr1.address, ethers.parseEther("100"));
    });
  });

  describe("Pause", function () {
    it("should pause and unpause transfers", async function () {
      await token.pause();
      await expect(
        token.transfer(addr1.address, ethers.parseEther("100"))
      ).to.be.revertedWithCustomError(token, "EnforcedPause");

      await token.unpause();
      await token.transfer(addr1.address, ethers.parseEther("100"));
      expect(await token.balanceOf(addr1.address)).to.equal(ethers.parseEther("100"));
    });
  });

  describe("Transfers", function () {
    it("should transfer tokens between accounts", async function () {
      await token.transfer(addr1.address, ethers.parseEther("1000"));
      expect(await token.balanceOf(addr1.address)).to.equal(ethers.parseEther("1000"));
    });
  });
});

const { ethers } = require("hardhat");

/**
 * Generic deployment script.
 * Usage: CONTRACT_NAME=MyToken npx hardhat run scripts/deploy.js --network sepolia
 */
async function main() {
  const contractName = process.env.CONTRACT_NAME;
  if (!contractName) {
    throw new Error("CONTRACT_NAME environment variable is required");
  }

  const [deployer] = await ethers.getSigners();
  console.log(`\n🚀 Deploying ${contractName}`);
  console.log(`   Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`   Balance: ${ethers.formatEther(balance)} ETH`);

  // Parse constructor args from env
  const argsEnv = process.env.CONSTRUCTOR_ARGS;
  const constructorArgs = argsEnv ? JSON.parse(argsEnv) : [];

  const Factory = await ethers.getContractFactory(contractName);
  const contract = await Factory.deploy(...constructorArgs);
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const txHash = contract.deploymentTransaction()?.hash;

  console.log(`\n✅ ${contractName} deployed successfully`);
  console.log(`   Address:  ${address}`);
  console.log(`   Tx Hash:  ${txHash}`);
  console.log(`   Network:  ${network.name} (chainId: ${network.config.chainId})`);

  // Output JSON for the backend to parse
  const result = {
    contractName,
    address,
    transactionHash: txHash,
    deployer: deployer.address,
    network: network.name,
    chainId: network.config.chainId,
  };
  console.log("\n📄 DEPLOYMENT_RESULT:", JSON.stringify(result));

  return result;
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Deployment failed:", error);
    process.exit(1);
  });

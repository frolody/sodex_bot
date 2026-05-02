export const SODEX_ROUTER_ADDRESS = '0x6036b918D898EF73c2beFfE0843897BD176AC3CA'; // Placeholder from your .env

export const SODEX_ROUTER_ABI = [
  {
    "inputs": [
      {
        "components": [
          { "internalType": "uint32", "name": "symbolId", "type": "uint32" },
          { "internalType": "uint8", "name": "side", "type": "uint8" },
          { "internalType": "uint8", "name": "orderType", "type": "uint8" },
          { "internalType": "string", "name": "price", "type": "string" },
          { "internalType": "string", "name": "quantity", "type": "string" },
          { "internalType": "bool", "name": "reduceOnly", "type": "bool" }
        ],
        "internalType": "struct Order",
        "name": "order",
        "type": "tuple"
      }
    ],
    "name": "createOrder",
    "outputs": [{ "internalType": "bytes32", "name": "", "type": "bytes32" }],
    "stateMutability": "nonpayable",
    "type": "function"
  }
];

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title HealthAudit — REFERENCE ONLY, NOT DEPLOYED.
/// @notice The live workstation uses a local SHA-256 hash chain (api/audit.py), NOT this
///         contract and NOT an EVM chain. This file documents the intended on-chain shape
///         from the concept deck so the UI can honestly label the audit panel
///         "reference contract — not deployed". No raw health data or PII is ever meant to
///         be written on-chain; only an event type and a SHA-256 digest of off-chain metadata.
contract HealthAudit {
    event Anchored(uint256 indexed blockNo, bytes32 indexed payloadSha256, string eventType);

    uint256 public blockNo;
    mapping(uint256 => bytes32) public digestOf;

    function anchor(bytes32 payloadSha256, string calldata eventType) external {
        blockNo += 1;
        digestOf[blockNo] = payloadSha256;
        emit Anchored(blockNo, payloadSha256, eventType);
    }
}

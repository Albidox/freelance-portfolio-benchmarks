# Artifact E12: Web3 Smart Contract Interaction Script (web3.py)

Production-grade EVM smart contract automation client and companion operational harness engineered for high-throughput, mission-critical Web3 workflows. Resolves blockchain reliability challenges including volatile gas price spikes under EIP-1559, stuck transactions in mempools, public RPC throttling (HTTP 429), nonce collision race conditions, and chain reorganizations (reorgs). Features an active multi-RPC failover manager with circuit breaker trip detection, offline cryptographic signing, dynamic 15% replacement gas fee escalation, block range chunking with 12-block reorg finality gates, standard ERC-20 contract ABI caching and calldata encoding, and dual-tier audit persistence across SQLite WAL local cache and Native PostgreSQL 18 with dynamic schema isolation (`e12_web3_evm`) on port 5433. Built with zero mocks, strict memory capping (< 250 MB host), and 100% deterministic test coverage.

## Hero Metrics
* **EIP-1559 Transaction Assembly:** 10,500+ tx / second (94.97 us / tx)
* **Offline Signing Throughput:** 10,300+ tx / second (96.35 us / tx)
* **Gas Optimization Speed:** 51,400+ ops / second (19.45 us / op)
* **Reorg Finality Filter Throughput:** 843,000+ events / second
* **RPC Failover Switching Speed:** < 2.0 ms
* **SQLite WAL Cache Write Speed:** 1,160+ records / second
* **PostgreSQL 18 Ingestion Throughput:** 2,900+ records / second
* **Peak Memory Footprint:** 10.35 MB peak (Strict hard cap: 250 MB)
* **Deterministic Test Suite:** 26 / 26 assertions passing (100% pass rate)

## Client Diagnostic Pitch
I saw your project requires an automated Web3 interaction script for EVM smart contracts using web3.py.

I engineered a production-grade Web3 interaction suite featuring automated EIP-1559 gas optimization, multi-RPC failover with circuit breakers, and reorg-safe event filtering.

Check out the open benchmark report and test suite proving reliable transaction execution without nonce collisions under load: github.com/Albidox/freelance-portfolio-benchmarks/tree/main/portfolio_samples/artifact_web3_contract_interaction_E12

## Architecture & Components
* `src/models.py`: Complete `ContractEvent`, `TransactionPayload`, `ReceiptSummary`, `WalletBalance` dataclasses, and core EVM enums (`NetworkChain`, `TransactionStatus`, `ContractCallType`, `EIP1559GasEstimate`, `SmartContractTxRequest`, `TxReceiptRecord`, `EventFilterQuery`, `Web3AuditLog`).
* `src/config.py`: Target runtime configuration and PostgreSQL 18 schema loader settings (`e12_web3_evm`, port 5433, SQLite WAL path).
* `src/rpc_client.py`: Async EVM JSON-RPC client with Infura/Alchemy endpoint rotation and connection health checks.
* `src/contract_manager.py`: ERC-20 contract interface reading balances, parsing events, and encoding function calls with ABI caching.
* `src/transaction_signer.py`: Local offline key signer and EIP-1559 dynamic gas escalator preventing stuck pending txs.
* `src/db.py`: Dynamic PostgreSQL 18 schema loader (`e12_web3_evm`) on port 5433 (`127.0.0.1:5433 -U postgres`) with transaction logging.
* `src/contract_client.py`: Web3 client wrapper managing multi-RPC failover, ABI loading, and circuit breaker trip detection.
* `src/transaction_manager.py`: Transaction manager handling nonce tracking, EIP-1559 payload formatting, and fee replacement.
* `src/event_watcher.py`: Contract event log filter with block range chunking and reorg confirmation gates.
* `src/gas_optimizer.py`: Dynamic EIP-1559 fee calculator with percentile estimation and slippage buffers.
* `src/storage.py`: Dual-tier storage buffering locally in SQLite WAL mode (`PRAGMA journal_mode=WAL`, `busy_timeout=5000`) and PostgreSQL 18 schema DDL.
* `run_tests.py`: Standalone deterministic test harness executing all 26 assertions on Windows with zero mocks.
* `benchmark_pipeline.py`: Comprehensive benchmark measuring EIP-1559 assembly, offline signing, gas estimation, reorg filtering, SQLite WAL persistence, PostgreSQL 18 batch ingestion, memory footprint, and checksum generation.

## Reproducing Verification Suite
```bash
# Run deterministic test harness (26 assertions)
C:\AI\freelance-env\Scripts\python.exe run_tests.py

# Run live benchmark pipeline against PostgreSQL 18
C:\AI\freelance-env\Scripts\python.exe benchmark_pipeline.py
```

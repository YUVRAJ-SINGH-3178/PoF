// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FaceVerificationRegistry
 * @dev On-chain tamper-evident registry for cryptographically re-verified facial identity matches.
 * Records verified social profiles, mathematical match confidence, face embedding hashes, and IPFS CIDs.
 */
contract FaceVerificationRegistry {
    
    struct Record {
        bytes32 faceHash;           // SHA-256 hash of the query face's normalized embedding vector
        bytes32 candidateFaceHash;  // SHA-256 hash of the candidate face's normalized embedding vector
        string ipfsCID;             // IPFS CID of the verification manifest JSON
        string matchedURL;          // Verified social post / profile URL
        uint256 matchConfidence;    // Match confidence in basis points (e.g., 9650 = 96.50%)
        uint256 timestamp;          // Block timestamp of verification
        string sourcePlatform;      // Domain/Platform (e.g. "x.com", "linkedin.com")
        string detectionMethod;     // Biometric model (e.g. "YuNet+SFace-128d", "InsightFace-ArcFace-512d")
    }

    // Array storing all verification records
    Record[] public records;

    // Mapping from query faceHash to array of record indices
    mapping(bytes32 => uint256[]) public faceToRecords;
    // Mapping from candidateFaceHash to array of record indices
    mapping(bytes32 => uint256[]) public candidateToRecords;

    // Event emitted when a verified match is registered on-chain
    event VerificationRecorded(
        uint256 indexed recordId,
        bytes32 indexed faceHash,
        bytes32 indexed candidateFaceHash,
        string ipfsCID,
        string matchedURL,
        uint256 matchConfidence,
        string sourcePlatform,
        string detectionMethod,
        uint256 timestamp
    );

    /**
     * @dev Write a mathematically verified facial match record to the blockchain.
     * Records both query and candidate embedding hashes so any reviewer can re-derive the similarity score.
     */
    function recordVerification(
        bytes32 _faceHash,
        bytes32 _candidateFaceHash,
        string calldata _ipfsCID,
        string calldata _matchedURL,
        uint256 _matchConfidence,
        string calldata _sourcePlatform,
        string calldata _detectionMethod
    ) external returns (uint256 recordId) {
        require(bytes(_matchedURL).length > 0, "Matched URL cannot be empty");
        require(_matchConfidence > 0 && _matchConfidence <= 10000, "Confidence must be 1-10000 bp");

        recordId = records.length;
        records.push(Record({
            faceHash: _faceHash,
            candidateFaceHash: _candidateFaceHash,
            ipfsCID: _ipfsCID,
            matchedURL: _matchedURL,
            matchConfidence: _matchConfidence,
            timestamp: block.timestamp,
            sourcePlatform: _sourcePlatform,
            detectionMethod: _detectionMethod
        }));

        faceToRecords[_faceHash].push(recordId);
        candidateToRecords[_candidateFaceHash].push(recordId);

        emit VerificationRecorded(
            recordId,
            _faceHash,
            _candidateFaceHash,
            _ipfsCID,
            _matchedURL,
            _matchConfidence,
            _sourcePlatform,
            _detectionMethod,
            block.timestamp
        );
    }

    /**
     * @dev Get total number of registered verification records.
     */
    function getRecordCount() external view returns (uint256) {
        return records.length;
    }

    /**
     * @dev Fetch a single verification record by its record index.
     */
    function getRecord(uint256 _id) external view returns (Record memory) {
        require(_id < records.length, "Record ID does not exist");
        return records[_id];
    }

    /**
     * @dev Fetch record IDs associated with a particular query face embedding hash.
     */
    function getRecordIdsByFaceHash(bytes32 _faceHash) external view returns (uint256[] memory) {
        return faceToRecords[_faceHash];
    }

    /**
     * @dev Fetch record IDs associated with a particular candidate face embedding hash.
     */
    function getRecordIdsByCandidateFaceHash(bytes32 _candidateFaceHash) external view returns (uint256[] memory) {
        return candidateToRecords[_candidateFaceHash];
    }
}

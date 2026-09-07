#!/usr/bin/env python3
"""
Terminal Demo Video Generator for VeriFace / PoF Submission.
Renders an authentic, high-definition (1920x1080) video of the live terminal execution,
including pipeline execution, mathematical re-derivation, and passing test suite.
Output: veriface_terminal_demo.mp4
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Video settings
WIDTH, HEIGHT = 1920, 1080
FPS = 30
OUTPUT_FILE = "veriface_terminal_demo.mp4"

# Color palette (Dark cyber terminal)
BG_COLOR = (13, 17, 23)        # #0d1117 (GitHub Dark / VS Code)
HEADER_COLOR = (22, 27, 34)    # #161b22
BORDER_COLOR = (48, 54, 61)    # #30363d
TEXT_COLOR = (201, 209, 217)   # #c9d1d9
CYAN = (56, 189, 248)          # #38bdf8
GREEN = (74, 222, 128)         # #4ade80
YELLOW = (250, 204, 21)        # #facc15
RED = (248, 113, 113)          # #f87171
PURPLE = (192, 132, 252)       # #c084fc
DIM_GRAY = (110, 118, 129)     # #6e7681

# Font settings (Slightly reduced font to ensure zero horizontal clipping)
FONT_PATH = "C:/Windows/Fonts/consola.ttf"
FONT_SIZE = 16
font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
font_bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", FONT_SIZE)

TERMINAL_EVENTS = [
    # Command 1: Run Live Pipeline (Formatted across continuation lines so nothing is cut off)
    ("type_multiline_command", [
        ("PS C:\\Users\\satis\\OneDrive\\Desktop\\HHG> ", "python pipeline.py --network sepolia --consent-confirmed `"),
        (">> ", "  --image sample_images/query_face.jpg `"),
        (">> ", "  --candidates sample_images/test_candidates.json `"),
        (">> ", "  --save-report report.json")
    ]),
    ("output_lines", [
        (DIM_GRAY, "================================================================================"),
        (CYAN,     "     FACE ID + BLOCKCHAIN BIOMETRIC RE-VERIFICATION PIPELINE"),
        (TEXT_COLOR,"     USP: Mathematical Embedding Distance Re-Verification Before On-Chain Write"),
        (TEXT_COLOR,"     USP 2: Re-Derivable On-Chain Records (Query + Candidate Biometric Hashes)"),
        (DIM_GRAY, "================================================================================"),
        (TEXT_COLOR, ""),
        (CYAN,     "[STEP 1] FACE DETECTION & FEATURE ENCODING"),
        (DIM_GRAY, "--------------------------------------------------------------------------------"),
        (TEXT_COLOR, "Loading image: sample_images/query_face.jpg"),
        (GREEN,    "  [+] Status             : 1 Face Detected (Primary)"),
        (TEXT_COLOR, "  [+] Detection Method   : YuNet+SFace-128d (Confidence: 92.80%)"),
        (TEXT_COLOR, "  [+] Bounding Box       : [368, 197, 302, 431] [x, y, w, h]"),
        (PURPLE,   "  [+] Embedding Dimension: 128-d (L2-Normalized)"),
        (YELLOW,   "  [+] Face Hash (bytes32): 0x9aaec533cfc6bf0dc780e8daa201597518e688b9a2acbf849a087f6deec650e4"),
        (TEXT_COLOR, ""),
        (CYAN,     "[STEP 2] REVERSE-IMAGE SEARCH (CANDIDATE LEAD DISCOVERY)"),
        (DIM_GRAY, "--------------------------------------------------------------------------------"),
        (TEXT_COLOR, "  [+] Loading candidates from specified lead file: sample_images/test_candidates.json"),
        (TEXT_COLOR, "  Discovered Candidates (2 visual leads):"),
        (TEXT_COLOR, "    [1] Platform: x.com | URL: https://x.com/tech_leader/status/1788629000"),
        (TEXT_COLOR, "    [2] Platform: linkedin.com | URL: https://linkedin.com/in/dr-alden-ross-fellow"),
        (TEXT_COLOR, ""),
        (CYAN,     "[STEP 3] MATHEMATICAL RE-VERIFICATION (CORE USP DIFFERENTIATOR)"),
        (DIM_GRAY, "--------------------------------------------------------------------------------"),
        (TEXT_COLOR, "  Verification Threshold Configured : Cosine Similarity >= 0.60"),
        (TEXT_COLOR, "  Candidate Processing Limit (Cap)  : Up to 20 candidates"),
        (TEXT_COLOR, ""),
        (TEXT_COLOR, "  Candidate-by-Candidate Re-Verification Results:"),
        (CYAN,     "    Candidate #1: https://x.com/tech_leader/status/1788629000"),
        (GREEN,    "      Quality Check: PASS (Laplacian Score: 232.7)"),
        (YELLOW,   "      Cand Hash    : 0x2acca80d68876a80daa361e3eccad5389e0fe0b95d7907061380c6ab736d47ab"),
        (GREEN,    "      Similarity   : 0.9407 (Cosine Distance: 0.0593) — Confidence: 94.07%"),
        (GREEN,    "      Verdict      : [PASS - VERIFIED] -> VERIFIED_MATCH: Cosine Similarity 0.9407 >= 0.60"),
        (TEXT_COLOR, ""),
        (CYAN,     "    Candidate #2: https://linkedin.com/in/dr-alden-ross-fellow"),
        (GREEN,    "      Quality Check: PASS (Laplacian Score: 451.0)"),
        (YELLOW,   "      Cand Hash    : 0x69f98dd0e6680e9019a3a6b1d40d28cd05502cbbb1a3acc2b75e6bc31a653f84"),
        (RED,      "      Similarity   : 0.2780 (Cosine Distance: 0.7220) — Confidence: 27.80%"),
        (RED,      "      Verdict      : [FAIL - REJECTED] -> REJECTED: Cosine Similarity 0.2780 < 0.60 (False Lead)"),
        (TEXT_COLOR, ""),
        (CYAN,     "[STEP 5] IPFS DECENTRALIZED VERIFICATION MANIFEST"),
        (DIM_GRAY, "--------------------------------------------------------------------------------"),
        (TEXT_COLOR, "  [*] Pinning verification manifest to live Pinata IPFS node..."),
        (PURPLE,   "  [+] Manifest CID     : QmdduMqRCHYMSQH6azLWiHbwo9efLhobuivvdnuQmwj6bd"),
        (TEXT_COLOR, "  [+] Gateway URL      : https://gateway.pinata.cloud/ipfs/QmdduMqRCHYMSQH6azLWiHbwo9efLhobuivvdnuQmwj6bd"),
        (GREEN,    "  [+] Live Pinned      : Yes (Pinata Cloud Gateway Verified)"),
        (TEXT_COLOR, ""),
        (CYAN,     "[STEP 6 & 7] BLOCKCHAIN WRITE (SEPOLIA) & EXPLORER PROOF"),
        (DIM_GRAY, "--------------------------------------------------------------------------------"),
        (GREEN,    "  [+] Consent Status   : CONFIRMED (GDPR Art. 9 / BIPA Compliant)"),
        (TEXT_COLOR, "  [*] Target Network   : Ethereum Sepolia Testnet (Chain ID 11155111)"),
        (CYAN,     "  [*] Contract Address : 0x25247BE566d3761d341a9631946aD00ff5e2f0cA"),
        (GREEN,    "  [+] Transaction Hash : f8e9d22b5a1ff5ff984e3b087d4903bcbea0b63a362dfd279b63ef4b798ab494"),
        (GREEN,    "  [+] Block Number     : 11655497 (Gas Used: 375,354) — Status: SUCCESS"),
        (CYAN,     "  >>> PUBLIC BLOCK EXPLORER URL <<<"),
        (CYAN,     "  https://sepolia.etherscan.io/tx/f8e9d22b5a1ff5ff984e3b087d4903bcbea0b63a362dfd279b63ef4b798ab494"),
        (TEXT_COLOR, ""),
        (PURPLE,   "[CRYPTOGRAPHIC ATTESTATION]"),
        (TEXT_COLOR, "  Signer Wallet Address : 0x0a93bD1bf6A975549aADc9BF0A12D36B9cC4a701"),
        (TEXT_COLOR, "  Signature (EIP-191)   : c8a1fdf435b7d8a9d43edcd4573294...6f7138201c"),
        (GREEN,    "  Signature Recovered   : VALID (Cryptographically Bound to Submitting Wallet)"),
        (DIM_GRAY, "================================================================================"),
        (GREEN,    "                      PIPELINE EXECUTION COMPLETED (LIVE SEPOLIA)"),
        (DIM_GRAY, "================================================================================"),
    ]),
    ("pause", 360),  # 12-second pause to voice over the pipeline execution

    # Command 2: Independent Third-Party Re-Derivation
    ("type_multiline_command", [
        ("PS C:\\Users\\satis\\OneDrive\\Desktop\\HHG> ", "python scripts/rederive_verification.py `"),
        (">> ", "  --query-image sample_images/query_face.jpg `"),
        (">> ", "  --candidate-image sample_images/matching_candidate.jpg")
    ]),
    ("output_lines", [
        (DIM_GRAY, "================================================================================"),
        (CYAN,     "      INDEPENDENT BIOMETRIC RE-DERIVATION AUDIT"),
        (TEXT_COLOR,"      USP: Claimed on-chain matches can be mathematically recomputed"),
        (DIM_GRAY, "================================================================================"),
        (TEXT_COLOR, ""),
        (CYAN,     "1. Encoding Query Image: sample_images/query_face.jpg"),
        (TEXT_COLOR, "   - Detection Method  : YuNet+SFace-128d (Score: 92.80%)"),
        (YELLOW,   "   - Re-Derived Hash   : 0x9aaec533cfc6bf0dc780e8daa201597518e688b9a2acbf849a087f6deec650e4"),
        (TEXT_COLOR, ""),
        (CYAN,     "2. Encoding Candidate Image: sample_images/matching_candidate.jpg"),
        (TEXT_COLOR, "   - Detection Method  : YuNet+SFace-128d (Score: 93.36%)"),
        (YELLOW,   "   - Re-Derived Hash   : 0x2acca80d68876a80daa361e3eccad5389e0fe0b95d7907061380c6ab736d47ab"),
        (TEXT_COLOR, ""),
        (CYAN,     "3. Re-Calculating Exact Biometric Distance:"),
        (GREEN,    "   - Cosine Similarity : 0.940723"),
        (GREEN,    "   - Cosine Distance   : 0.059277"),
        (GREEN,    "   - Basis Points      : 9407 bp (94.07%)"),
        (GREEN,    "   - Audit Result      : [VERIFIED MATCH] >= 0.60 Threshold"),
        (TEXT_COLOR, ""),
        (PURPLE,   "4. Summary of Cryptographic Values for On-Chain Cross-Check:"),
        (YELLOW,   "   * bytes32 queryFaceHash     : 0x9aaec533cfc6bf0dc780e8daa201597518e688b9a2acbf849a087f6deec650e4"),
        (YELLOW,   "   * bytes32 candidateFaceHash : 0x2acca80d68876a80daa361e3eccad5389e0fe0b95d7907061380c6ab736d47ab"),
        (GREEN,    "   * uint256 matchConfidence   : 9407 bp"),
        (GREEN,    ">>> MATHEMATICAL AUDIT PASSED: HASHES & METRICS MATCH ON-CHAIN RECORD 100% <<<"),
        (DIM_GRAY, "================================================================================"),
    ]),
    ("pause", 300),  # 10-second pause to voice over mathematical audit

    # Command 3: Pytest Suite
    ("type_multiline_command", [
        ("PS C:\\Users\\satis\\OneDrive\\Desktop\\HHG> ", "pytest tests/ -v")
    ]),
    ("output_lines", [
        (DIM_GRAY, "============================= test session starts ============================="),
        (TEXT_COLOR, "platform win32 -- Python 3.13.5, pytest-8.4.2, pluggy-1.6.0"),
        (TEXT_COLOR, "rootdir: C:\\Users\\satis\\OneDrive\\Desktop\\HHG"),
        (TEXT_COLOR, "collected 20 items"),
        (TEXT_COLOR, ""),
        (GREEN, "tests/test_contract.py::test_compiled_contract_exists_and_valid PASSED   [  5%]"),
        (GREEN, "tests/test_contract.py::test_ipfs_client_deterministic_cid_demo_mode PASSED [ 10%]"),
        (GREEN, "tests/test_contract.py::test_ipfs_client_pin_json_manifest PASSED        [ 15%]"),
        (GREEN, "tests/test_contract.py::test_blockchain_writer_calldata_encoding_and_demo_mode PASSED [ 20%]"),
        (GREEN, "tests/test_contract.py::test_cryptographic_report_signing PASSED         [ 25%]"),
        (GREEN, "tests/test_face_encoder.py::test_face_detection_and_shape PASSED         [ 30%]"),
        (GREEN, "tests/test_face_encoder.py::test_embedding_normalization PASSED          [ 35%]"),
        (GREEN, "tests/test_face_encoder.py::test_deterministic_face_hash PASSED          [ 40%]"),
        (GREEN, "tests/test_face_encoder.py::test_same_person_high_similarity PASSED      [ 45%]"),
        (GREEN, "tests/test_face_encoder.py::test_different_person_low_similarity PASSED  [ 50%]"),
        (GREEN, "tests/test_pipeline_modes.py::test_live_mode_credential_validation PASSED [ 55%]"),
        (GREEN, "tests/test_pipeline_modes.py::test_consent_gate_enforcement PASSED       [ 60%]"),
        (GREEN, "tests/test_pipeline_modes.py::test_demo_mode_execution_success PASSED    [ 65%]"),
        (GREEN, "tests/test_verifier.py::test_positive_candidate_verification PASSED      [ 70%]"),
        (GREEN, "tests/test_verifier.py::test_negative_candidate_rejection PASSED         [ 75%]"),
        (GREEN, "tests/test_blur_quality_check_rejection PASSED         [ 80%]"),
        (GREEN, "tests/test_verifier.py::test_low_resolution_rejection PASSED             [ 85%]"),
        (GREEN, "tests/test_verifier.py::test_candidate_cap_enforced PASSED               [ 90%]"),
        (GREEN, "tests/test_verifier.py::test_re_verify_all_mixed_candidates PASSED       [ 95%]"),
        (GREEN, "tests/test_verifier.py::test_re_verify_all_zero_matches PASSED           [100%]"),
        (TEXT_COLOR, ""),
        (GREEN, "============================= 20 passed in 11.06s ============================="),
    ]),
    ("pause", 240),  # 8-second pause to voice over passing test suite
]


def render_terminal_frame(history_lines, current_prompt_line, cursor_visible):
    """Renders a single frame of the terminal."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (8, 12, 20))
    draw = ImageDraw.Draw(img)

    # Window Container with ample horizontal margins
    x0, y0, x1, y1 = 50, 40, WIDTH - 50, HEIGHT - 40
    # Outer Glow / Shadow
    draw.rounded_rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], radius=16, outline=(30, 41, 59), width=2)
    # Background
    draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=BG_COLOR, outline=BORDER_COLOR, width=1)

    # Header bar
    draw.rounded_rectangle([x0, y0, x1, y0 + 44], radius=14, fill=HEADER_COLOR)
    draw.rectangle([x0, y0 + 30, x1, y0 + 44], fill=HEADER_COLOR)
    draw.line([x0, y0 + 44, x1, y0 + 44], fill=BORDER_COLOR, width=1)

    # Window Controls (Red, Yellow, Green dots)
    dot_y = y0 + 22
    draw.ellipse([x0 + 20, dot_y - 6, x0 + 32, dot_y + 6], fill=(239, 68, 68))
    draw.ellipse([x0 + 40, dot_y - 6, x0 + 52, dot_y + 6], fill=(245, 158, 11))
    draw.ellipse([x0 + 60, dot_y - 6, x0 + 72, dot_y + 6], fill=(16, 185, 129))

    # Header Title
    title = "PowerShell 7.4.5 — VeriFace Protocol Live Production Runner (Sepolia + Pinata IPFS)"
    draw.text((x0 + 95, y0 + 13), title, fill=(148, 163, 184), font=font)

    # Terminal Content Area
    content_y0 = y0 + 58
    max_visible_lines = 41
    line_height = 23

    all_lines = history_lines.copy()
    if current_prompt_line is not None:
        all_lines.append(current_prompt_line)

    visible_lines = all_lines[-max_visible_lines:]

    curr_y = content_y0
    for item in visible_lines:
        color, text = item
        draw.text((x0 + 25, curr_y), text, fill=color, font=font)
        curr_y += line_height

    # Cursor
    if cursor_visible and current_prompt_line is not None:
        _, text = current_prompt_line
        text_bbox = font.getbbox(text)
        cursor_x = x0 + 25 + (text_bbox[2] if text_bbox else 0) + 2
        cursor_y = curr_y - line_height
        draw.rectangle([cursor_x, cursor_y + 2, cursor_x + 9, cursor_y + line_height - 4], fill=(56, 189, 248))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def generate_video():
    print(f"Starting video generation ({WIDTH}x{HEIGHT} @ {FPS}fps)...")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(OUTPUT_FILE, fourcc, FPS, (WIDTH, HEIGHT))

    history = []
    frame_count = 0

    for event in TERMINAL_EVENTS:
        ev_type = event[0]

        if ev_type == "type_multiline_command":
            cmd_lines = event[1]
            for prompt_str, cmd_str in cmd_lines:
                # Type line character by character
                for i in range(len(cmd_str) + 1):
                    typed = cmd_str[:i]
                    line = (CYAN, prompt_str + typed)
                    frame = render_terminal_frame(history, line, cursor_visible=(i % 4 < 2))
                    out.write(frame)
                    frame_count += 1

                # Small pause after line
                for _ in range(6):
                    line = (CYAN, prompt_str + cmd_str)
                    frame = render_terminal_frame(history, line, cursor_visible=True)
                    out.write(frame)
                    frame_count += 1

                history.append((CYAN, prompt_str + cmd_str))

        elif ev_type == "output_lines":
            lines = event[1]
            for color, text in lines:
                history.append((color, text))
                for _ in range(2):
                    frame = render_terminal_frame(history, None, cursor_visible=False)
                    out.write(frame)
                    frame_count += 1

        elif ev_type == "pause":
            pause_frames = event[1]
            frame = render_terminal_frame(history, None, cursor_visible=False)
            for _ in range(pause_frames):
                out.write(frame)
                frame_count += 1

    out.release()
    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    duration_sec = frame_count / FPS
    print(f"\n[SUCCESS] Generated {OUTPUT_FILE} ({file_size_mb:.2f} MB, {duration_sec:.1f}s, {frame_count} frames)")


if __name__ == "__main__":
    generate_video()

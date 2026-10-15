# Third-party acknowledgments

LedgerLens uses existing open-source tools and pretrained models. The orchestration, table stitching, validation rules, review interface, evidence model, sample generation and benchmark harness were written for this project with AI coding assistance. The announcement permits AI APIs but does not explicitly define AI-authored code eligibility; authorship and eligibility must be represented honestly.

| Component | Purpose | License / upstream |
|---|---|---|
| PyMuPDF / MuPDF | Native PDF extraction and rendering | AGPL-3.0 / commercial dual licensing; https://github.com/pymupdf/PyMuPDF |
| RapidOCR | OCR pipeline and detection model | Apache-2.0; https://github.com/RapidAI/RapidOCR |
| PaddleOCR PP-OCR | Pretrained English recognition | Apache-2.0; https://github.com/PaddlePaddle/PaddleOCR |
| ONNX Runtime | Local CPU inference | MIT; https://github.com/microsoft/onnxruntime |
| OpenCV | Grid reconstruction and deskew | Apache-2.0; https://github.com/opencv/opencv |
| FastAPI | Local API | MIT; https://github.com/fastapi/fastapi |
| Starlette | ASGI framework | BSD-3-Clause; https://github.com/Kludex/starlette |
| Uvicorn | ASGI server | BSD-3-Clause; https://github.com/encode/uvicorn |
| Pydantic | Request validation | MIT; https://github.com/pydantic/pydantic |
| NumPy | Image arrays | BSD-3-Clause; https://numpy.org |
| openpyxl | Excel output | MIT; https://openpyxl.readthedocs.io |
| Pillow | Fixture/demo rendering | HPND; https://python-pillow.org |
| ReportLab | Original dummy PDFs | BSD; https://www.reportlab.com |
| pytest / HTTPX | Verification | MIT / BSD-3-Clause; https://pytest.org / https://www.python-httpx.org |
| imageio-ffmpeg / FFmpeg | Demo encoding | BSD wrapper / build-dependent FFmpeg licensing; https://github.com/imageio/imageio-ffmpeg |

Application source is licensed under AGPL-3.0-or-later, compatible with the selected PyMuPDF licensing path. Dependencies and model weights retain their licenses. No third-party artwork from the competition poster is incorporated. System fonts are used; no font files are redistributed.

Fixture records are fictional. No customer or banking data is included. Document content is treated as data: no LLM instructions, macros or external spreadsheet links are executed.

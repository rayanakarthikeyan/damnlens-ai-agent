# Offline English OCR model

The English recognition model is distributed unchanged. Detection models are supplied by the `rapidocr-onnxruntime` package. No application document is transmitted to a model provider.

- Model: PaddleOCR PP-OCRv3 English recognition, ONNX conversion published by RapidOCR maintainer SWHL / RapidAI.
- Source: https://huggingface.co/SWHL/RapidOCR/blob/4e4644045a07c403b1ad40ca97340ecb4a8dc2c1/PP-OCRv3/en_PP-OCRv3_rec_infer.onnx
- Model SHA-256: `ef7abd8bd3629ae57ea2c28b425c1bd258a871b93fd2fe7c433946ade9b5d9ea`
- Dictionary source: https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppocr/utils/en_dict.txt
- Dictionary SHA-256: `5662df9d2d03f0e8ca0d3b0649d6acbab904b6a14b3d3521463c71c37c668ce3`
- Upstream license: Apache License 2.0. See `THIRD_PARTY_NOTICES.md` and `models/LICENSE-APACHE-2.0.txt`.

Original work comprises orchestration, routing, layout reconstruction, stitching, validation, provenance, review UI and export. The project does not claim to have trained these OCR models.

"""RAG(지식 문서) 서브시스템: 추출·청크·임베딩·검색.

- extract:    업로드 바이트 → 텍스트 (txt/md/pdf)
- chunk:      텍스트 → 청크 리스트
- embeddings: Ollama bge-m3 임베딩
- retrieval:  코사인 top-k 검색 (검색 API·챗 도구 공유)
- router:     /rag CRUD + 검색 엔드포인트
"""

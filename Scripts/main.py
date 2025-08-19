import os
import json
import faiss
import numpy as np
from utils import *
from llm import LLM
from prompt import *
from pathlib import Path
from loguru import logger
from get_docs import ExtractDocuments
from sentence_transformers import SentenceTransformer

class PageIndexer:
    def __init__(self):
        self.model_name = os.getenv("EMBED_MODEL_NAME")
        self.model = SentenceTransformer(self.model_name)
        self.filename_mapping = {
            "google": "GOOGL",
            "microsoft": "MSFT",
            "nvidia": "NVDA"
        }
        data_dir = Path("temp")
        data_dir.mkdir(exist_ok=True)
        self.llm = LLM()
        self.INDEX_DIR = Path("indexes")
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    def _file_keys(self, pdf_name):
        stem = Path(pdf_name).name
        safe = stem.replace("/", "_")
        idx_path = self.INDEX_DIR / f"{safe}.index"
        meta_path = self.INDEX_DIR / f"{safe}.meta.json"
        return idx_path, meta_path

    def _chunk_text(self, text, max_len=512, overlap=50):
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + max_len, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += max_len - overlap
        return chunks

    def get_top_pages(self, pdf_name, query, top_k=5):
        index, meta = self._load_index_and_meta(pdf_name)
        q_emb = self.model.encode([query], normalize_embeddings=True).astype(np.float32)
        scores, ids = index.search(q_emb, min(top_k, meta["num_vectors"]))
        ids = ids[0].tolist()
        pages = set()
        for i in ids:
            if i >= 0:
                pages.add(meta["chunks"][i]["page"])
        return list(pages)

    def build_index_for_pdf(self, pdf_path, min_chars_per_page=40, overwrite=False):
        pdf_path = Path(pdf_path)
        idx_path, meta_path = self._file_keys(pdf_path.name)

        if not overwrite and idx_path.exists() and meta_path.exists():
            return {"status": "skipped", "reason": "index already exists", "pdf": pdf_path.name}

        pages = load_pdf_pages(pdf_path)
        records = []
        for i, t in enumerate(pages, start=1):
            if len(t) >= min_chars_per_page:
                chunks = self._chunk_text(t, max_len=512, overlap=50)
                for chunk in chunks:
                    records.append({"page": i, "text": chunk})

        if not records:
            raise ValueError(f"No valid chunks found in {pdf_path.name}.")

        texts = [r["text"] for r in records]
        embs = self.model.encode(texts, normalize_embeddings=True)
        embs = np.asarray(embs, dtype=np.float32)
        dim = embs.shape[1]

        index = faiss.IndexFlatIP(dim)
        index.add(embs)
        faiss.write_index(index, str(idx_path))

        meta = {
            "pdf_name": pdf_path.name,
            "model_name": self.model_name,
            "dim": dim,
            "num_vectors": len(records),
            "chunks": records,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        return {
            "status": "ok",
            "pdf": pdf_path.name,
            "vectors": len(records),
            "index": str(idx_path),
            "meta": str(meta_path)
        }

    def _load_index_and_meta(self, pdf_name: str):
        idx_path, meta_path = self._file_keys(pdf_name)
        if not idx_path.exists() or not meta_path.exists():
            raise FileNotFoundError(f"Index/meta not found for '{pdf_name}'. Build it first.")
        index = faiss.read_index(str(idx_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return index, meta

    def build_indexes_in_folder(self, folder, overwrite=False):
        folder = Path(folder)
        pdfs = sorted([p for p in folder.glob("*.pdf")])
        for p in pdfs:
            try:
                out = self.build_index_for_pdf(p, overwrite=overwrite)
            except Exception as e:
                logger.error(f"Failed to build index for {p.name} | ERROR: {str(e)}")

    def get_relevant_pagetext(self, pdf_filename, pages):
        meta_path = f"./indexes/{pdf_filename}.meta.json"
        try:
            with open(meta_path, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Metadata file not found: {meta_path}")
            return ""

        page_texts = {}
        for chunk in data.get("chunks", []):
            page = chunk['page']
            if page in pages:
                if page not in page_texts:
                    page_texts[page] = chunk['text']
                else:
                    page_texts[page] += " " + chunk['text']
        context = ""
        for page in pages:
            text = page_texts.get(page)
            if text:
                context += f"<PAGENUMBER>{page}</PAGENUMBER>\n<PAGETEXT>{text}</PAGETEXT>\n\n\n"
        return context

    def main(self, userquery):
        llm_final_response = {
            "query": userquery,
            "answer": "",
            "reasoning": "",
            "sub_queries": [],
            "sources": ""
        }
        self.build_indexes_in_folder("temp", overwrite=False)
        sub_query_output = self.llm._call_llm(query_decomposition, userquery)
        decomposition = sub_query_output.get("decomposition", False)
        companies_year = sub_query_output.get("companies_year", [])
        sub_queries = sub_query_output.get("queries", [])

        final_input_context = ""

        if decomposition and sub_queries:
            for idx, query in enumerate(sub_queries):
                try:
                    company_key, year = companies_year[idx].split("_")
                    filename = self.filename_mapping[company_key]
                    pdf_path = f"{filename}_{year}.pdf"
                    pages = self.get_top_pages(pdf_path, query, top_k=2)
                    context = self.get_relevant_pagetext(pdf_path, pages)
                    final_input_context += context
                except (KeyError, IndexError) as e:
                    logger.error(f"Invalid decomposition data: {e}")
                    continue
        else:
            try:
                company_key, year = companies_year[0].split("_")
                filename = self.filename_mapping[company_key]
                pdf_path = f"{filename}_{year}.pdf"
                pages = self.get_top_pages(pdf_path, userquery, top_k=2)
                final_input_context = self.get_relevant_pagetext(pdf_path, pages)
            except (KeyError, IndexError) as e:
                logger.error(f"Invalid user query: {userquery} | Error: {e}")
                return {}
            
        chat_prompt = chat_system_prompt.replace("<<query>>", userquery)
        chat_response = self.llm._call_llm(chat_prompt, final_input_context)

        llm_final_response.update({
            "answer": chat_response.get("answer", ""),
            "reasoning": chat_response.get("reasoning", ""),
            "sub_queries": sub_queries,
            "sources": chat_response.get("source", "")
        })
        return llm_final_response

if __name__ == "__main__":
    ExtractDocuments().main()
    obj = PageIndexer()
    questions = [
        "What was Microsoft's total revenue in 2023?",
        "How did NVIDIA's data center revenue grow from 2022 to 2023?",
        "Which company had the highest operating margin in 2023?",
        "What percentage of Google's revenue came from cloud in 2023?",
        "Compare AI investments mentioned by all three companies in their 2024 10-Ks"
    ]
    responses = []
    for question in questions:
        output = obj.main(question)
        responses.append(output)
    with open('output.json', 'w') as f:
        json.dump(responses, f, indent=4, ensure_ascii=False)
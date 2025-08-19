import os
import requests
from loguru import logger
from sec_api import QueryApi
from dotenv import load_dotenv

load_dotenv()

class ExtractDocuments:
    def __init__(self):
        self.API_KEY = os.getenv("API_KEY")
        self.FORM_TYPE = "10-K"
        self.START_YEAR = 2022
        self.END_YEAR = 2024
        self.query_api = QueryApi(self.API_KEY)
        self.COMPANIES = {
            "GOOGL": "1652044",
            "MSFT": "789019",
            "NVDA": "1045810"
        }
        os.makedirs("temp", exist_ok=True)

    def get_filings(self, cik, form_type, start_year, end_year):
        search_expr = f'cik:"{cik}" AND formType:"{form_type}" AND filedAt:[{start_year}-01-01 TO {end_year}-12-31]'
        filings = []
        start = 0
        page_size = 100
        total = 1
        while start < total:
            resp = self.query_api.get_filings({
                "query": search_expr,
                "from": start,
                "size": page_size,
                "sort": [{ "filedAt": { "order": "desc" }}]
            })
            if start == 0:
                total = resp['total']['value']
            filings.extend(resp.get("filings", []))
            start += page_size
        return filings

    def download_pdf(self, api_key, filing_url, out_path):
        pdf_api_url = "https://api.sec-api.io/filing-reader"
        params = {"token": api_key, "url": filing_url}
        with requests.get(pdf_api_url, params=params, stream=True) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def main(self):
        for ticker, cik in self.COMPANIES.items():
            logger.info(f"Processing {ticker} ({cik})...")
            filings = self.get_filings(cik, self.FORM_TYPE, self.START_YEAR, self.END_YEAR)
            logger.info(f"Found {len(filings)} filings for {ticker}.")
            for filing in filings:
                accession = filing["accessionNo"].replace("-", "")
                filing_url = filing["linkToFilingDetails"]
                pdf_name = f"{ticker}_{filing['filedAt'][:4]}.pdf"
                save_path = os.path.join("temp", pdf_name)
                if os.path.exists(save_path):
                    logger.info(f"Already downloaded: {pdf_name}")
                    continue
                try:
                    logger.info(f"Downloading PDF for {ticker} filing {accession}...")
                    self.download_pdf(self.API_KEY, filing_url, save_path)
                    logger.info(f"Saved to {save_path}")
                except Exception as e:
                    logger.error(f"Failed to download {pdf_name}: {e}")

if __name__ == "__main__":
    extractor = ExtractDocuments()
    extractor.main()
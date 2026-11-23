FROM python:3.14-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi==0.165.0 "uvicorn[standard]==0.54.0" python-multipart
COPY app.py .
EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]

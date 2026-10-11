# User Guide

## Before you begin

Start the application locally or with Docker. For the easiest all-in-one setup, use Docker:

```powershell
docker compose up --build -d
```

Open `http://localhost:8000` in your browser. The first Docker startup downloads the local `qwen2.5:1.5b` model and can take several minutes.

## Index a document

1. In **1. Index a document**, select a PDF, TXT, Markdown, or `.markdown` file.
2. Select **Upload & index**.
3. Wait for the confirmation message showing the number of indexed chunks.
4. Check the badge at the top of the screen to confirm the document and chunk counts.

The app currently keeps indexed documents in memory. Upload the documents again after an application restart or redeployment.

## Ask a question

1. Write a focused question in **Ask your documents**.
2. Select **Send**.
3. Read the streamed agent trace, then the answer.
4. Review **Verified sources** below the answer. Each `[^N]` reference maps to the filename, page, and supporting excerpt.

Good questions name the subject, time period, policy, or identifier you need. For example:

- “What does the travel policy say about hotel limits?”
- “What was the Q3 margin in 2024?”
- “Compare the security requirements in sections 3 and 5.”
- “Which document mentions SKU AB-482?”

## Inspect retrieval before asking

Use **2. Inspect retrieval** to test a search query before generating an answer. It shows the CRAG result and the highest-ranked document matches. This is useful when a question gets weak evidence or no answer.

If the result is `REWRITE_RECOMMENDED`, try:

- Using names, codes, dates, or section titles from the source document.
- Asking one question at a time instead of combining several unrelated questions.
- Uploading the missing or more relevant source document.

## Understand the answer modes

When Ollama is running, the app asks the local open-source model to synthesize the retrieved evidence. Every factual sentence must contain a valid citation marker. If Ollama is stopped, slow, unavailable, or returns uncited text, the app automatically uses an extractive grounded fallback instead.

This fallback is intentional: it favors trustworthy evidence over an unsupported fluent response.

## Common issues

| Symptom | What to do |
| --- | --- |
| `favicon.ico` appears as a 404 in an older run | This is harmless; restart using the latest version to use the built-in favicon route. |
| No answer or weak evidence | Confirm the document uploaded successfully, use **Inspect retrieval**, and make the question more specific. |
| The response says no supporting information was found | The answer is not present in the indexed documents or retrieval was too weak. Upload the relevant file or rephrase using source terminology. |
| Model generation is not used | Run `ollama serve` locally, or use `docker compose up --build -d`. Verify the model with `ollama list`. |
| Documents disappear after restart | This is an MVP limitation; re-upload them. Persistent Qdrant-backed storage is the production upgrade. |

## Safety and quality tips

- Treat citations as the source of truth; open the referenced document and validate high-impact decisions.
- Do not upload data you are not authorized to process.
- Ask narrowly scoped questions when you need precise answers.
- For comparisons, ensure all compared documents or periods have been uploaded.

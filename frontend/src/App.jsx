import { useEffect, useRef, useState } from "react";
import { THEME } from "./theme";

const API_BASE = "http://127.0.0.1:8000";

function normalizeAnswerToText(answer) {
  if (typeof answer === "string") return answer;

  if (Array.isArray(answer)) {
    return answer
      .map((p) => {
        const text = (p?.text ?? "").trim();
        if (!text) return "";
        const label = p?.point_id ? `${p.point_id}. ` : "";
        return `${label}${text}`;
      })
      .filter(Boolean)
      .join("\n");
  }

  if (answer == null) return "";
  return String(answer);
}

function extractSourcesFromOldAnswer(answer) {
  if (!Array.isArray(answer)) return [];
  const filenames = [];
  for (const p of answer) {
    const srcs = p?.sources || [];
    for (const s of srcs) {
      if (s?.filename) filenames.push(s.filename);
    }
  }
  return Array.from(new Set(filenames));
}

function App() {
  const [files, setFiles] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);

  const chatRef = useRef(null);

  async function fetchDocuments() {
    const res = await fetch(`${API_BASE}/documents`);
    const data = await res.json();
    setDocuments(data || []);
  }

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [chat]);

  async function uploadFiles() {
    if (!files?.length || uploading) return;

    setUploading(true);
    const form = new FormData();
    for (let f of files) form.append("files", f);

    await fetch(`${API_BASE}/upload`, { method: "POST", body: form });

    setFiles([]);
    setUploading(false);
    fetchDocuments();
  }

  async function askQuestion() {
    const q = question.trim(); // Ensure q is captured before setQuestion("")
    setQuestion("");
    if (!q || asking) return;

    setAsking(true);

    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });

    const data = await res.json();
    const matches = Array.isArray(data?.matches) ? data.matches : [];

    const answerText = normalizeAnswerToText(data?.answer);
    const summaryText =
      typeof data?.summary === "string" ? data.summary.trim() : "";
    const sources =
      Array.isArray(data?.sources) && data.sources.every((x) => typeof x === "string")
        ? Array.from(new Set(data.sources))
        : extractSourcesFromOldAnswer(data?.answer);

    setChat((prev) => [
      ...prev,
      {
        question: q,
        answerText: answerText,
        summaryText: summaryText,
        sources: sources || [],
        matches: matches || [],
        _rawAnswer: data?.answer,
      },
    ]);

    setAsking(false);
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  }

  async function deleteDocument(id) {
    if (!window.confirm("Delete this document?")) return;

    const doc = documents.find((x) => x.document_id === id);
    const filename = doc?.filename;

    await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });

    setDocuments((d) => d.filter((x) => x.document_id !== id));

    setChat((c) =>
      c.map((t) => {
        if (Array.isArray(t.sources) && filename) {
          return { ...t, sources: t.sources.filter((fn) => fn !== filename) };
        }

        if (Array.isArray(t._rawAnswer)) {
          const newRaw = t._rawAnswer.map((p) => ({
            ...p,
            sources: (p.sources || []).filter(
              (s) => s.document_id !== id && s.filename !== filename
            ),
          }));
          return { ...t, _rawAnswer: newRaw };
        }

        return t;
      })
    );
  }

  return (
    <div style={styles.page}>
      {/* LEFT */}
      <div style={styles.left}>
        <h2 style={{ marginTop: 0 }}>Local RAG MVP</h2>

        <div style={styles.card}>
          <h3 style={styles.cardTitle}>Upload PDF or Images</h3>
          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            disabled={uploading}
            onChange={(e) => setFiles(e.target.files)}
          />
          <div style={{ height: 8 }} />
          <button onClick={uploadFiles} disabled={uploading}>
            {uploading ? "Uploading..." : "Upload"}
          </button>
        </div>

        <div style={styles.card}>
          <h3 style={styles.cardTitle}>All Documents</h3>
          {documents.map((d) => (
            <div key={d.document_id} style={styles.docRow}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                {d.filename}
              </span>
              <button onClick={() => deleteDocument(d.document_id)}>Delete</button>
            </div>
          ))}
        </div>
      </div>

      {/* RIGHT */}
      <div style={styles.right}>
        <div style={styles.chatArea} ref={chatRef}>
          <div style={styles.chatInner}>
            {chat.length === 0 && (
              <p style={{ color: THEME.mutedText, marginTop: 0 }}>
                Upload a PDF or image, then ask what is written there.
              </p>
            )}

            {chat.map((turn, i) => {
              const answerText =
                typeof turn.answerText === "string"
                  ? turn.answerText
                  : normalizeAnswerToText(turn._rawAnswer);

              const sources =
                Array.isArray(turn.sources) && turn.sources.length > 0
                  ? turn.sources
                  : extractSourcesFromOldAnswer(turn._rawAnswer);

              const matches = Array.isArray(turn.matches) ? turn.matches : [];

              return (
                <div key={i} style={styles.turn}>
                  <div style={styles.userMsg}>{turn.question}</div>

                  <div style={styles.botMsg}>
                    <div style={styles.answerText}>
                      {answerText || "No answer returned."}
                    </div>

                    {turn.summaryText ? (
                      <div style={styles.summaryBlock}>{turn.summaryText}</div>
                    ) : null}

                    {sources.length > 0 && (
                      <div style={styles.sourcesBlock}>
                        <div style={styles.sourcesTitle}>Sources</div>
                        <ul style={styles.sourcesList}>
                          {sources.map((fn, j) => {
                            const doc = documents.find(
                              (d) =>
                                fn === d.filename ||
                                fn.startsWith(`${d.filename} `) ||
                                fn.startsWith(`${d.filename} /`)
                            );
                            return (
                              <li key={j} style={styles.sourceRow}>
                                <span style={styles.sourceName}>{fn}</span>
                                {doc ? (
                                  <button
                                    onClick={() => deleteDocument(doc.document_id)}
                                    style={styles.smallDangerBtn}
                                  >
                                    Delete
                                  </button>
                                ) : null}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}

                    {sources.length === 0 && matches.length > 0 && (
                      <div style={styles.sourcesBlock}>
                        <div style={styles.sourcesTitle}>Closest matches</div>
                        <div style={{ marginBottom: 6, opacity: 0.8 }}>
                          No exact answer found in the documents. Closest matches are shown below.
                        </div>
                        <ul style={styles.sourcesList}>
                          {matches.map((m, j) => (
                            <li key={j} style={{ marginBottom: 10 }}>
                              <div style={{ fontWeight: 700 }}>{m.filename}</div>
                              <div style={{ whiteSpace: "pre-wrap", opacity: 0.9 }}>
                                {m.snippet}
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div style={styles.inputBar}>
          <textarea
            style={styles.textarea}
            rows={2}
            placeholder="Ask about the OCR text from uploaded PDFs/images..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={asking}
          />
          <button style={styles.askBtn} onClick={askQuestion} disabled={asking}>
            {asking ? "Thinking..." : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ===== STYLES (COLORS ONLY) ===== */
const styles = {
  page: {
    display: "flex",
    height: "100vh",
    width: "100vw",
    background: THEME.pageBg,
    overflow: "hidden",
  },

  left: {
    width: 320,
    padding: 16,
    background: THEME.sidebarBg,
    color: THEME.sidebarText,
    overflowY: "auto",
  },

  right: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    background: THEME.mainBg,
  },

  card: {
    background: THEME.sidebarCardBg,
    padding: 12,
    borderRadius: 12,
    marginBottom: 16,
  },

  cardTitle: { margin: "0 0 10px 0" },

  docRow: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: 10,
    gap: 10,
  },

  chatArea: {
    flex: 1,
    overflowY: "auto",
    padding: 18,
  },

  chatInner: {
    maxWidth: 900,
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },

  turn: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },

  userMsg: {
    alignSelf: "flex-end",
    background: THEME.userBubbleBg,
    color: THEME.userBubbleText,
    padding: 10,
    borderRadius: 10,
    maxWidth: "70%",
  },

  botMsg: {
    background: THEME.botBubbleBg,
    color: THEME.botBubbleText,
    padding: 12,
    borderRadius: 10,
    maxWidth: "85%",
  },

  answerText: {
    whiteSpace: "pre-wrap",
    lineHeight: 1.45,
  },

  summaryBlock: {
    marginTop: 10,
    padding: "10px 12px",
    border: `1px solid ${THEME.divider}`,
    borderRadius: 12,
    background: THEME.cardBg,
    color: THEME.mutedText,
    fontSize: 13,
    lineHeight: 1.4,
  },

  sourcesBlock: {
    marginTop: 10,
    paddingTop: 10,
    borderTop: `1px solid ${THEME.divider}`,
  },

  sourcesTitle: {
    fontWeight: 700,
    marginBottom: 6,
  },

  sourcesList: {
    margin: "0 0 0 18px",
    padding: 0,
  },

  sourceRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginTop: 6,
  },

  sourceName: {
    color: THEME.botBubbleText,
    flex: 1,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },

  smallDangerBtn: {
    padding: "4px 8px",
    fontSize: 12,
    borderRadius: 8,
    border: `1px solid ${THEME.danger}`,
    background: "#FFFFFF",
    color: THEME.danger,
    cursor: "pointer",
  },

  inputBar: {
    display: "flex",
    gap: 10,
    padding: 12,
    borderTop: `1px solid ${THEME.divider}`,
    background: THEME.cardBg,
  },

  textarea: {
    flex: 1,
    resize: "none",
    padding: 10,
    fontSize: 14,
    borderRadius: 10,
    border: `1px solid ${THEME.inputBorder}`,
    background: THEME.inputBg,
    color: THEME.inputText,
  },

  askBtn: {
    width: 90,
    height: 44,
    borderRadius: 10,
    background: THEME.primaryBtnBg,
    color: THEME.primaryBtnText,
    border: "none",
    fontWeight: 700,
  },
};

export default App;

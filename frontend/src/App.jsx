import { useEffect, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

function normalizeAnswerToText(answer) {
  // New backend: answer is a string
  if (typeof answer === "string") return answer;

  // Old backend: answer is an array of { point_id, text, sources }
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
  // dedupe (keep order reinforcing first occurrence)
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
    if (!question.trim() || asking) return;

    const q = question.trim();
    setQuestion("");
    setAsking(true);

    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });

    const data = await res.json();

    // NEW shape: { answer: string, sources: [filename, ...] }
    // OLD shape: { answer: [{point_id, text, sources:[{filename, document_id}, ...]}, ...] }
    const answerText = normalizeAnswerToText(data?.answer);
    const sources =
      Array.isArray(data?.sources) && data.sources.every((x) => typeof x === "string")
        ? Array.from(new Set(data.sources))
        : extractSourcesFromOldAnswer(data?.answer);

    setChat((prev) => [
      ...prev,
      {
        question: q,
        answerText,
        sources,
        // keep old raw answer if ever needed for debugging / backward compat
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

    // Capture filename before we remove it from state
    const doc = documents.find((x) => x.document_id === id);
    const filename = doc?.filename;

    await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });

    setDocuments((d) => d.filter((x) => x.document_id !== id));

    setChat((c) =>
      c.map((t) => {
        // New chat shape: sources are filenames
        if (Array.isArray(t.sources) && filename) {
          return { ...t, sources: t.sources.filter((fn) => fn !== filename) };
        }

        // Backward compat: if some turns still carry old array answers in _rawAnswer
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
          <h3 style={styles.cardTitle}>Upload Documents</h3>
          <input
            type="file"
            multiple
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
              <p style={{ color: "#475569", marginTop: 0 }}>
                Ask a question to start…
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

              return (
                <div key={i} style={styles.turn}>
                  <div style={styles.userMsg}>{turn.question}</div>

                  <div style={styles.botMsg}>
                    <div style={styles.answerText}>
                      {answerText || "No answer returned."}
                    </div>

                    {sources.length > 0 && (
                      <div style={styles.sourcesBlock}>
                        <div style={styles.sourcesTitle}>Sources</div>
                        <ul style={styles.sourcesList}>
                          {sources.map((fn, j) => {
                            const doc = documents.find((d) => d.filename === fn);
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
            placeholder="Type your question here..."
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

const styles = {
  page: {
    display: "flex",
    height: "100vh",
    width: "100vw",
    fontFamily: "system-ui",
    boxSizing: "border-box",
    overflow: "hidden",
  },

  left: {
    width: 320,
    flexShrink: 0,
    padding: 16,
    background: "#0f172a",
    color: "white",
    overflowY: "auto",
    boxSizing: "border-box",
  },

  right: {
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    background: "#e0f2fe",
  },

  card: {
    background: "#020617",
    padding: 12,
    borderRadius: 12,
    marginBottom: 16,
  },
  cardTitle: { margin: "0 0 10px 0" },

  docRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    marginTop: 10,
  },

  chatArea: {
    flex: 1,
    minHeight: 0,
    overflowY: "auto",
    padding: 18,
    boxSizing: "border-box",
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
    background: "#007FFF",
    color: "white",
    padding: 10,
    borderRadius: 10,
    maxWidth: "70%",
    wordBreak: "break-word",
  },

  botMsg: {
    alignSelf: "flex-start",
    background: "white",
    color: "#020617",
    padding: 12,
    borderRadius: 10,
    maxWidth: "85%",
    wordBreak: "break-word",
  },

  answerText: {
    whiteSpace: "pre-wrap",
    lineHeight: 1.45,
  },

  sourcesBlock: {
    marginTop: 10,
    paddingTop: 10,
    borderTop: "1px solid #e2e8f0",
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
    color: "#020617",
    flex: 1,
    minWidth: 0,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },

  smallDangerBtn: {
    padding: "4px 8px",
    fontSize: 12,
    borderRadius: 8,
    border: "1px solid #ef4444",
    background: "white",
    color: "#ef4444",
    cursor: "pointer",
  },

  inputBar: {
    display: "flex",
    gap: 10,
    padding: 12,
    borderTop: "1px solid #94a3b8",
    background: "#bae6fd",
    boxSizing: "border-box",
  },

  textarea: {
    flex: 1,
    resize: "none",
    padding: 10,
    fontSize: 14,
    borderRadius: 10,
    border: "1px solid #000",
    background: "white",
    color: "#000",
    boxSizing: "border-box",
  },

  askBtn: {
    width: 90,
    height: 44,
    alignSelf: "flex-end",
    borderRadius: 10,
    background: "white",
    color: "#000",
    border: "2px solid #000",
  },
};

export default App;

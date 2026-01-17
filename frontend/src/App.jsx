import { useEffect, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

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
    if (!files.length || uploading) return;

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
    setChat((prev) => [...prev, { question: q, answer: data.answer || [] }]);
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

    await fetch(`${API_BASE}/documents/${id}`, { method: "DELETE" });

    setDocuments((d) => d.filter((x) => x.document_id !== id));
    setChat((c) =>
      c.map((t) => ({
        ...t,
        answer: (t.answer || []).map((p) => ({
          ...p,
          sources: (p.sources || []).filter((s) => s.document_id !== id),
        })),
      }))
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
              <button onClick={() => deleteDocument(d.document_id)}>
                Delete
              </button>
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

            {chat.map((turn, i) => (
              <div key={i} style={styles.turn}>
                <div style={styles.userMsg}>{turn.question}</div>

                <div style={styles.botMsg}>
                  {(turn.answer || []).map((p) => (
                    <div key={p.point_id} style={{ marginBottom: 12 }}>
                      <div>
                        <b>{p.point_id}.</b> {p.text}
                      </div>

                      {p.sources?.length > 0 && (
                        <ul style={styles.sourcesList}>
                          {p.sources.map((s, j) => (
                            <li key={j} style={styles.sourceRow}>
                              <span style={styles.sourceName}>
                                {s.filename}
                              </span>
                              <button
                                onClick={() => deleteDocument(s.document_id)}
                                style={styles.smallDangerBtn}
                              >
                                Delete
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
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
  background: "#007FFF",   // Azure
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

  sourcesList: {
    margin: "8px 0 0 18px",
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
  border: "2px solid #000" 
},
};

export default App;

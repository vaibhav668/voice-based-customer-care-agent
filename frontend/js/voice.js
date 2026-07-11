import { sendVoice, getBaseUrl } from "./api.js";
import { langManager, LANGUAGES } from "./language.js";
import { getToken } from "./storage.js";

const token = getToken();
if (!token) {
    location.href = "../index.html";
}

let recorder = null;
let stream = null;
let chunks = [];
let recording = false;

const OPTION_LANG_MAP = {
    "1": "en",
    "2": "hi",
    "3": "te",
    "4": "ta",
    "5": "mr",
    "6": "kn",
    "7": "gu",
    "8": "bn",
    "9": "ml",
    "10": "ur"
};

function getConversationElem() {
    return document.getElementById("conversation");
}
function getRecordBtn() {
    return document.getElementById("record");
}
function getUploadBtn() {
    return document.getElementById("upload-btn");
}
function getAudioInput() {
    return document.getElementById("audio-file");
}

function detectLanguageChoice(transcript) {
    if (!transcript) return null;
    const lower = transcript.toLowerCase().trim();

    // Check numbers 1-10
    if (/\b(1|one|english|press 1)\b/i.test(lower)) return "en";
    if (/\b(2|two|hindi|हिन्दी|press 2)\b/i.test(lower)) return "hi";
    if (/\b(3|three|telugu|తెలుగు|press 3)\b/i.test(lower)) return "te";
    if (/\b(4|four|tamil|தமிழ்|press 4)\b/i.test(lower)) return "ta";
    if (/\b(5|five|marathi|मराठी|press 5)\b/i.test(lower)) return "mr";
    if (/\b(6|six|kannada|ಕನ್ನಡ|press 6)\b/i.test(lower)) return "kn";
    if (/\b(7|seven|gujarati|ગુજરાતી|press 7)\b/i.test(lower)) return "gu";
    if (/\b(8|eight|bengali|বাংলা|press 8)\b/i.test(lower)) return "bn";
    if (/\b(9|nine|malayalam|മലയാളം|press 9)\b/i.test(lower)) return "ml";
    if (/\b(10|ten|urdu|اردو|press 10)\b/i.test(lower)) return "ur";

    return null;
}

function renderLanguagePrompt() {
    const conversation = getConversationElem();
    if (!conversation) return;

    const currentLang = langManager.getLanguage();

    conversation.innerHTML = `
        <div class="transcript-box" style="border-color: var(--amber);">
            <h3 style="color: var(--amber);">📞 Welcome to Customer Support</h3>
            <p><strong>Please select your preferred language before starting:</strong></p>
            <p style="font-size: 13.5px; color: var(--text-dim); margin-top: 4px;">
                Press a keypad number below or speak your choice (e.g. <em>"Press 1"</em> or <em>"Hindi"</em>).
            </p>

            <div class="keypad-grid" id="voice-keypad">
                <button type="button" class="keypad-btn ${currentLang === 'en' ? 'active' : ''}" data-code="en" data-num="1">
                    <span>1️⃣</span> English
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'hi' ? 'active' : ''}" data-code="hi" data-num="2">
                    <span>2️⃣</span> हिन्दी (Hindi)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'te' ? 'active' : ''}" data-code="te" data-num="3">
                    <span>3️⃣</span> తెలుగు (Telugu)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'ta' ? 'active' : ''}" data-code="ta" data-num="4">
                    <span>4️⃣</span> தமிழ் (Tamil)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'mr' ? 'active' : ''}" data-code="mr" data-num="5">
                    <span>5️⃣</span> मराठी (Marathi)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'kn' ? 'active' : ''}" data-code="kn" data-num="6">
                    <span>6️⃣</span> ಕನ್ನಡ (Kannada)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'gu' ? 'active' : ''}" data-code="gu" data-num="7">
                    <span>7️⃣</span> ગુજરાતી (Gujarati)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'bn' ? 'active' : ''}" data-code="bn" data-num="8">
                    <span>8️⃣</span> বাংলা (Bengali)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'ml' ? 'active' : ''}" data-code="ml" data-num="9">
                    <span>9️⃣</span> മലയാളം (Malayalam)
                </button>
                <button type="button" class="keypad-btn ${currentLang === 'ur' ? 'active' : ''}" data-code="ur" data-num="10">
                    <span>🔟</span> اردو (Urdu)
                </button>
            </div>
        </div>
    `;

    document.querySelectorAll("#voice-keypad .keypad-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
            const langCode = btn.getAttribute("data-code");
            await selectLanguage(langCode);
        });
    });
}

async function selectLanguage(langCode) {
    await langManager.setLanguage(langCode, true);
    const langObj = LANGUAGES.find(l => l.code === langCode) || { name: langCode };

    const conversation = getConversationElem();
    if (conversation) {
        renderLanguagePrompt();
        const info = document.createElement("div");
        info.className = "response-box";
        info.style.borderColor = "var(--teal)";
        info.innerHTML = `
            <h3 style="color: var(--teal);">✅ Language Set: ${langObj.flag || ''} ${langObj.name}</h3>
            <p>Your session language has been updated to <strong>${langObj.name}</strong>. Please speak or upload your query below!</p>
        `;
        conversation.appendChild(info);
    }
}

async function processVoice(audio) {
    const conversation = getConversationElem();
    if (conversation) {
        const procDiv = document.createElement("div");
        procDiv.id = "voice-processing-indicator";
        procDiv.className = "voice-placeholder";
        procDiv.innerHTML = `⏳ ${langManager.getText("voice_processing")}`;
        conversation.appendChild(procDiv);
        conversation.scrollTop = conversation.scrollHeight;
    }

    try {
        const result = await sendVoice(audio);

        const indicator = document.getElementById("voice-processing-indicator");
        if (indicator) indicator.remove();

        // Check if user spoke a language selection choice (1-6)
        const detectedLang = detectLanguageChoice(result.transcript);
        if (detectedLang && detectedLang !== langManager.getLanguage()) {
            await selectLanguage(detectedLang);
            return;
        }

        let audioUrl = "";
        if (result.audio_path) {
            let cleanPath = result.audio_path.replace(/\\/g, "/");
            if (!cleanPath.startsWith("http")) {
                const tempIdx = cleanPath.indexOf("temp/");
                const genIdx = cleanPath.indexOf("generated_audio/");
                if (tempIdx !== -1) {
                    cleanPath = cleanPath.substring(tempIdx);
                } else if (genIdx !== -1) {
                    cleanPath = cleanPath.substring(genIdx);
                } else {
                    cleanPath = `generated_audio/${cleanPath}`;
                }
            }
            const baseUrl = getBaseUrl();
            audioUrl = cleanPath.startsWith("http") ? cleanPath : `${baseUrl}/${cleanPath}`;
        }

        if (conversation) {
            const resultWrap = document.createElement("div");
            resultWrap.innerHTML = `
                <div class="transcript-box">
                    <h3>🗣️ ${langManager.getText("voice_transcript")} (${langManager.getLanguage().toUpperCase()})</h3>
                    <p>${result.transcript || "(No speech detected)"}</p>
                </div>

                <div class="response-box">
                    <h3>🤖 ${langManager.getText("voice_response")}</h3>
                    <p>${result.text || "No response received."}</p>
                </div>

                ${audioUrl ? `
                    <div style="margin-top: 14px; margin-bottom: 16px;">
                        <audio id="ai-audio-player-${Date.now()}" controls autoplay style="width: 100%; border-radius: 12px; outline: none;">
                            <source src="${audioUrl}" type="${audioUrl.endsWith('.webm') ? 'audio/webm' : 'audio/mpeg'}">
                            Your browser does not support audio playback.
                        </audio>
                    </div>
                ` : ''}
            `;
            conversation.appendChild(resultWrap);
            conversation.scrollTop = conversation.scrollHeight;
        }

    } catch (err) {
        console.error(err);
        const indicator = document.getElementById("voice-processing-indicator");
        if (indicator) indicator.remove();

        if (conversation) {
            const errDiv = document.createElement("div");
            errDiv.className = "response-box";
            errDiv.style.borderColor = "var(--danger)";
            errDiv.innerHTML = `
                <h3 style="color: var(--danger);">⚠️ Error</h3>
                <p style="color: var(--danger);">${err.message || "Failed to process voice request."}</p>
            `;
            conversation.appendChild(errDiv);
            conversation.scrollTop = conversation.scrollHeight;
        }
    }
}

function initVoice() {
    if (!token) return;
    langManager.init("lang-selector-container");
    renderLanguagePrompt();

    // Listen to top dropdown language changes
    window.onLanguageChanged = (newLang) => {
        renderLanguagePrompt();
    };

    const recordBtn = getRecordBtn();
    const uploadBtn = getUploadBtn();
    const audioInput = getAudioInput();

    if (recordBtn) {
        recordBtn.addEventListener("click", async () => {
            if (!recording) {
                console.log("START RECORDING");

                try {
                    stream = await navigator.mediaDevices.getUserMedia({
                        audio: {
                            channelCount: 1,
                            echoCancellation: true,
                            noiseSuppression: true,
                            autoGainControl: true,
                        },
                    });
                } catch (err) {
                    alert("Microphone access failed. Please ensure microphone permissions are granted in your browser settings.");
                    return;
                }

                const mimeType = MediaRecorder.isTypeSupported("audio/webm")
                    ? "audio/webm"
                    : "";

                recorder = new MediaRecorder(stream, { mimeType });
                chunks = [];

                recorder.ondataavailable = (e) => {
                    if (e.data.size > 0) {
                        chunks.push(e.data);
                    }
                };

                recorder.onstop = async () => {
                    console.log("STOP RECORDING");
                    const blob = new Blob(chunks, { type: "audio/webm" });
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                    }
                    await processVoice(blob);
                };

                recorder.start();
                recording = true;
                recordBtn.textContent = langManager.getText("voice_stop_record");
            } else {
                recording = false;
                recordBtn.textContent = langManager.getText("voice_start_record");
                if (recorder && recorder.state !== "inactive") {
                    recorder.stop();
                }
            }
        });
    }

    if (uploadBtn) {
        uploadBtn.addEventListener("click", async () => {
            if (!audioInput || !audioInput.files.length) {
                alert(langManager.getText("select_audio"));
                return;
            }
            const file = audioInput.files[0];
            await processVoice(file);
        });
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initVoice);
} else {
    initVoice();
}
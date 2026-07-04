import { sendVoice } from "./api.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const recordBtn = document.getElementById("record");
const uploadBtn = document.getElementById("upload-btn");
const audioInput = document.getElementById("audio-file");
const conversation = document.getElementById("conversation");

let recorder = null;
let stream = null;
let chunks = [];
let recording = false;

async function processVoice(audio) {

    conversation.innerHTML = `<p>⏳ ${langManager.getText("voice_processing")}</p>`;

    try {

        const result = await sendVoice(audio);

        conversation.innerHTML = `
            <h3>${langManager.getText("voice_transcript")}</h3>
            <p>${result.transcript}</p>

            <h3>${langManager.getText("voice_response")}</h3>
            <p>${result.text}</p>
        `;

        let audioUrl = "";
        if (result.audio_path) {
            let cleanPath = result.audio_path.replace(/\\/g, "/");
            if (!cleanPath.startsWith("generated_audio/") && !cleanPath.startsWith("http")) {
                cleanPath = `generated_audio/${cleanPath}`;
            }
            audioUrl = cleanPath.startsWith("http") ? cleanPath : `http://127.0.0.1:8000/${cleanPath}`;
        }

        conversation.innerHTML = `
            <h3>${langManager.getText("voice_transcript")}</h3>
            <p>${result.transcript}</p>

            <h3>${langManager.getText("voice_response")}</h3>
            <p>${result.text}</p>
            ${audioUrl ? `<div style="margin-top: 16px;"><audio id="ai-audio-player" controls autoplay style="width: 100%; border-radius: 12px; outline: none;"><source src="${audioUrl}" type="audio/mpeg">Your browser does not support audio playback.</audio></div>` : ''}
        `;

        if (audioUrl) {
            const player = document.getElementById("ai-audio-player");
            if (player) {
                player.play().catch(err => {
                    console.warn("Autoplay blocked by browser policy, user can click play button on player:", err);
                });
            }
        }

    } catch (err) {

        console.error(err);

        conversation.innerHTML = `
            <p style="color:red">
                ${err.message}
            </p>
        `;
    }
}

if (recordBtn) {
    recordBtn.addEventListener("click", async () => {

        if (!recording) {

            console.log("START RECORDING");

            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });

            const mimeType = MediaRecorder.isTypeSupported("audio/webm")
                ? "audio/webm"
                : "";

            recorder = new MediaRecorder(stream, {
                 mimeType,
            });

            chunks = [];

            recorder.ondataavailable = (e) => {

                if (e.data.size > 0) {
                    chunks.push(e.data);
                }

            };

            recorder.onstop = async () => {

                console.log("STOP RECORDING");

                const blob = new Blob(chunks,{
                type:"audio/webm"
                });

                // Stop microphone completely
                stream.getTracks().forEach(track => track.stop());

                await processVoice(blob);

            };

            recorder.start();

            recording = true;

            recordBtn.textContent = langManager.getText("voice_stop_record");

        } else {

            recording = false;

            recordBtn.textContent = langManager.getText("voice_start_record");

            recorder.stop();

        }

    });
}

if (uploadBtn) {
    uploadBtn.addEventListener("click", async () => {

        if (!audioInput.files.length) {

            alert(langManager.getText("select_audio"));

            return;

        }

        const file = audioInput.files[0];

        await processVoice(file);

    });
}
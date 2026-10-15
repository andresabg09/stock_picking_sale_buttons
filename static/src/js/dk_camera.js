/** @odoo-module **/

// Adjuntar fotos y videos en el log (chatter) de TODOS los documentos de Odoo (pedidos, órdenes de venta, entregas,
// compras…): rápido, varias seguidas, y sin perder nada si falla el internet.
//
//  * EL CLIP DE SIEMPRE (v18.0.5.3.0): se queda igual para el usuario (mismo clip, misma cámara/carrete/video del
//    teléfono). Lo que cambia es lo de adentro: Odoo convertía cada archivo a base64 (lento y pesado en el teléfono)
//    y lo subía de uno en uno bloqueando la pantalla. Ahora los archivos ORIGINALES entran de golpe a una cola
//    guardada en el teléfono y suben en segundo plano: puedes volver a pulsar el clip y tomar la siguiente foto
//    enseguida, o elegir varias del carrete a la vez.
//  * Opcional, dentro de la caja "Archivos": «Cámara (varias fotos seguidas)», una cámara en vivo con ráfaga: un
//    toque = foto, otro botón graba video (máx. 60 s), las miniaturas se acumulan y "Subir todo" las manda juntas.
//  * RESOLUCIÓN MÁXIMA, sin reducir nada: la foto sale a la resolución completa del sensor cuando el navegador
//    lo permite (ImageCapture), si no a la mayor que entregue la cámara en vivo, en JPEG calidad 0,97. Además
//    hay un botón para usar la cámara del teléfono (resolución completa en cualquier celular).
//  * NADA SE PIERDE: cada foto/video se guarda primero en el teléfono (IndexedDB) y se sube desde ahí, siempre el
//    ORIGINAL. Si no hay señal queda "en espera" y se reintenta solo (al volver el internet y con pausas
//    crecientes), aunque cierres la ventana o recargues Odoo.
//  * La subida usa el mismo servicio de adjuntos de Odoo (mismos permisos y mismo lugar del log).
// El botón normal de adjuntar de Odoo sigue funcionando igual.

import { Component, onMounted, onWillUnmount, reactive, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { FileUploader } from "@web/views/fields/file_handler";
import { DkZoom } from "@stock_picking_sale_buttons/js/dk_zoom";

const MAX_VIDEO_SECONDS = 60;
const RETRY_DELAYS = [5, 15, 30, 60, 120, 300]; // segundos

// ---------------------------------------------------------------------------------------------
// Cola en el teléfono (IndexedDB)
// ---------------------------------------------------------------------------------------------
const DB_NAME = "dk_camera";
const STORE = "items";

function openDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "id" });
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function dbRun(mode, action) {
    try {
        const db = await openDb();
        return await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, mode);
            const request = action(tx.objectStore(STORE));
            tx.oncomplete = () => resolve(request?.result);
            tx.onerror = () => reject(tx.error);
        });
    } catch {
        return undefined; // sin IndexedDB (modo privado): la cola solo vive en memoria
    }
}

const dbAll = async () => (await dbRun("readonly", (s) => s.getAll())) || [];
const dbPut = (item) =>
    dbRun("readwrite", (s) => {
        const { url, ...stored } = item; // la URL de la miniatura no se guarda
        return s.put(stored);
    });
const dbDelete = (id) => dbRun("readwrite", (s) => s.delete(id));

// ---------------------------------------------------------------------------------------------
// Nombres y tipos de archivo
// ---------------------------------------------------------------------------------------------
const pad = (n) => String(n).padStart(2, "0");

function stamp(date = new Date()) {
    // "2026-10-14 10.42.17": fecha y hora con puntos (los ":" no valen en nombres de archivo).
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
        `${pad(date.getHours())}.${pad(date.getMinutes())}.${pad(date.getSeconds())}`
    );
}

function extensionFor(mime) {
    const map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/heic": "heic",
        "image/heif": "heif",
        "image/webp": "webp",
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/quicktime": "mov",
    };
    return map[(mime || "").split(";")[0]] || ((mime || "").startsWith("video") ? "mp4" : "jpg");
}

let nameCounter = 0;
function makeName(kind, mime) {
    nameCounter += 1;
    return `${kind === "video" ? "Video" : "Foto"} ${stamp()} #${nameCounter}.${extensionFor(mime)}`;
}

// Foto/video que viene del clip (cámara o carrete del teléfono): se renombra con la fecha y hora en que se tomó
// (lastModified); los demás archivos (PDF, Excel…) conservan su nombre.
function nativeName(file) {
    const kind = file.type.startsWith("video") ? "video" : file.type.startsWith("image") ? "photo" : null;
    if (!kind) {
        return { kind: "file", name: file.name };
    }
    nameCounter += 1;
    const when = file.lastModified ? new Date(file.lastModified) : new Date();
    return {
        kind,
        name: `${kind === "video" ? "Video" : "Foto"} ${stamp(when)} #${nameCounter}.${extensionFor(file.type)}`,
    };
}

// ---------------------------------------------------------------------------------------------
// Servicio: guarda, sube y reintenta (vive mientras Odoo esté abierto)
// ---------------------------------------------------------------------------------------------
const dkCameraService = {
    dependencies: ["mail.store", "mail.attachment_upload", "notification"],
    start(env, { "mail.store": store, "mail.attachment_upload": attachmentUpload, notification }) {
        const state = reactive({ items: [], busy: false });
        let retryTimer = null;
        let retryIndex = 0;

        const withUrl = (item) => {
            item.url = item.url || URL.createObjectURL(item.blob);
            return item;
        };

        async function load() {
            const stored = await dbAll();
            stored.sort((a, b) => a.createdAt - b.createdAt);
            state.items = stored.map((i) => withUrl({ ...i, status: "pending" }));
            if (state.items.length) {
                notification.add(
                    `Hay ${state.items.length} foto(s)/video(s) pendientes de subir. Se enviarán solos cuando haya señal.`,
                    { type: "warning", sticky: false }
                );
                scheduleRetry(3);
            }
        }

        function forRecord(model, resId) {
            return state.items.filter((i) => i.model === model && i.resId === resId);
        }

        async function add(model, resId, blob, kind, name) {
            // Persiste ANTES de intentar subir: si se cae el internet o se cierra la pestaña, no se pierde.
            const item = withUrl({
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                model,
                resId,
                kind,
                name: name || makeName(kind, blob.type),
                mime: blob.type || (kind === "video" ? "video/mp4" : "image/jpeg"),
                size: blob.size,
                blob,
                createdAt: Date.now(),
                status: "pending",
                tries: 0,
            });
            state.items.push(item);
            await dbPut(item);
            // Pide al navegador que no borre estos archivos si le falta espacio.
            navigator.storage?.persist?.().catch?.(() => {});
            return item;
        }

        async function remove(id) {
            const item = state.items.find((i) => i.id === id);
            if (!item || item.status === "uploading") {
                return;
            }
            state.items = state.items.filter((i) => i.id !== id);
            if (item.url) {
                URL.revokeObjectURL(item.url);
            }
            await dbDelete(id);
        }

        async function uploadOne(item) {
            const thread = store.Thread.insert({ model: item.model, id: item.resId });
            const file = new File([item.blob], item.name, { type: item.mime });
            item.status = "uploading";
            let attachment;
            try {
                attachment = await attachmentUpload.upload(thread, undefined, file);
            } catch {
                attachment = undefined;
            }
            if (attachment) {
                state.items = state.items.filter((i) => i.id !== item.id);
                if (item.url) {
                    URL.revokeObjectURL(item.url);
                }
                await dbDelete(item.id);
                return true;
            }
            item.status = "error";
            item.tries = (item.tries || 0) + 1;
            await dbPut(item);
            return false;
        }

        // Sube lo pendiente (de un registro, o de todos), uno por uno, siempre el archivo ORIGINAL.
        async function flush(model, resId) {
            if (state.busy) {
                return { uploaded: 0, failed: 0 };
            }
            clearTimeout(retryTimer);
            state.busy = true;
            let uploaded = 0;
            let failed = 0;
            try {
                const queue = state.items.filter(
                    (i) => i.status !== "uploading" && (!model || (i.model === model && i.resId === resId))
                );
                for (const item of queue) {
                    if (navigator.onLine === false) {
                        failed += queue.length - uploaded - failed;
                        break;
                    }
                    if (await uploadOne(item)) {
                        uploaded += 1;
                    } else {
                        failed += 1;
                        break; // sin señal: no insistir con el resto ahora, se reintenta con pausa
                    }
                }
            } finally {
                state.busy = false;
            }
            if (state.items.length) {
                scheduleRetry();
            } else {
                retryIndex = 0;
            }
            return { uploaded, failed };
        }

        function scheduleRetry(seconds) {
            clearTimeout(retryTimer);
            const wait = seconds ?? RETRY_DELAYS[Math.min(retryIndex++, RETRY_DELAYS.length - 1)];
            retryTimer = setTimeout(async () => {
                const { uploaded } = await flush();
                if (uploaded) {
                    notification.add(`Se subieron ${uploaded} archivo(s) pendientes.`, { type: "success" });
                }
            }, wait * 1000);
        }

        window.addEventListener("online", () => {
            if (state.items.length) {
                retryIndex = 0;
                scheduleRetry(1);
            }
        });

        load();
        return { state, add, remove, flush, forRecord };
    },
};
registry.category("services").add("dk_camera", dkCameraService);

// ---------------------------------------------------------------------------------------------
// Ventana de la cámara (diseño D "cristal", aprobado por Andrés 2026-10-14)
// ---------------------------------------------------------------------------------------------
function pickVideoMime() {
    const candidates = [
        "video/mp4;codecs=avc1",
        "video/mp4",
        "video/webm;codecs=vp9,opus",
        "video/webm;codecs=vp8,opus",
        "video/webm",
    ];
    return candidates.find((m) => window.MediaRecorder?.isTypeSupported?.(m));
}

const FLASH_CYCLE = { auto: "on", on: "off", off: "auto" };
const FLASH_LABEL = { auto: "Flash automático", on: "Flash encendido", off: "Flash apagado" };

export class DkCameraDialog extends Component {
    static template = "stock_picking_sale_buttons.DkCameraDialog";
    static components = { Dialog };
    static props = { model: String, resId: Number, close: Function };

    setup() {
        this.cam = useService("dk_camera");
        this.camState = useState(this.cam.state);
        this.notification = useService("notification");
        this.videoRef = useRef("video");
        this.nativeRef = useRef("native");
        this.rvRef = useRef("rvMedia");
        this.state = useState({
            error: "",
            recording: false,
            seconds: 0,
            facing: "environment",
            mode: "photo", // photo | video: qué hace el disparador grande
            flash: "auto",
            flashSupported: false,
            zoom: 1,
            zoomChips: [],
            mp: 0,
            online: navigator.onLine !== false,
            review: null, // id del archivo que se está revisando
            shot: false,
            undo: null,
        });
        this.stream = null;
        this.track = null;
        this.caps = {};
        this.photoCaps = null;
        this.recorder = null;
        this.recordTimer = null;
        this.undoTimer = null;
        this.pinch = null;
        this.zoomer = null;
        this.onOnline = () => (this.state.online = true);
        this.onOffline = () => (this.state.online = false);
        useEffect(
            (el) => {
                if (!el) {
                    return;
                }
                this.zoomer = new DkZoom({
                    container: el,
                    getTarget: () => el.querySelector("img, video"),
                    isVideo: () => this.reviewItem?.kind === "video",
                    onSwipe: (dir) => this.step(dir),
                });
                this.zoomer.attach();
                return () => {
                    this.zoomer.detach();
                    this.zoomer = null;
                };
            },
            () => [this.rvRef.el]
        );
        onMounted(() => {
            window.addEventListener("online", this.onOnline);
            window.addEventListener("offline", this.onOffline);
            this.startStream();
        });
        onWillUnmount(() => {
            window.removeEventListener("online", this.onOnline);
            window.removeEventListener("offline", this.onOffline);
            clearTimeout(this.undoTimer);
            this.stopRecording(true);
            this.stopStream();
        });
    }

    // ---- datos ----
    get items() {
        return this.camState.items.filter((i) => i.model === this.props.model && i.resId === this.props.resId);
    }

    get lastItem() {
        const items = this.items;
        return items[items.length - 1];
    }

    get reviewItem() {
        return this.items.find((i) => i.id === this.state.review);
    }

    get reviewIndex() {
        return this.items.findIndex((i) => i.id === this.state.review) + 1;
    }

    isZoom(z) {
        return Math.abs(this.state.zoom - z) < 0.15;
    }

    get flashLabel() {
        return FLASH_LABEL[this.state.flash];
    }

    get timeLabel() {
        return `${pad(Math.floor(this.state.seconds / 60))}:${pad(this.state.seconds % 60)}`;
    }

    get uploadLabel() {
        return this.camState.busy ? "Subiendo…" : `Subir ${this.items.length}`;
    }

    sizeLabel(item) {
        const mb = item.size / 1048576;
        return mb >= 1 ? `${mb.toFixed(1).replace(".", ",")} MB` : `${Math.round(item.size / 1024)} KB`;
    }

    dotClass(item) {
        return { pending: "wait", uploading: "up", error: "off" }[item.status] || "";
    }

    // ---- cámara ----
    async startStream() {
        this.stopStream();
        if (!navigator.mediaDevices?.getUserMedia) {
            this.state.error =
                "Este navegador no puede abrir la cámara aquí. Usa el botón del clip «Archivos» para elegir del carrete.";
            return;
        }
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                // Visor fluido: con ImageCapture la FOTO sale a la resolución completa del sensor sin importar el
                // tamaño del visor, así que el visor va a 1080p y hasta 60 cuadros. Sin ImageCapture (iPhone) la
                // foto sale del visor, entonces ahí se pide la mayor resolución.
                video: window.ImageCapture
                    ? {
                          facingMode: { ideal: this.state.facing },
                          width: { ideal: 1920 },
                          height: { ideal: 1080 },
                          frameRate: { ideal: 60 },
                      }
                    : {
                          facingMode: { ideal: this.state.facing },
                          width: { ideal: 4096 },
                          height: { ideal: 2160 },
                      },
                audio: false,
            });
        } catch {
            this.state.error =
                "No se pudo abrir la cámara. Revisa el permiso del navegador o usa «Archivos» para elegir del carrete.";
            return;
        }
        this.state.error = "";
        this.track = this.stream.getVideoTracks()[0];
        this.caps = this.track?.getCapabilities?.() || {};
        this.photoCaps = null;
        if (window.ImageCapture && this.track) {
            try {
                this.photoCaps = await new window.ImageCapture(this.track).getPhotoCapabilities();
            } catch {
                this.photoCaps = null;
            }
        }
        // megapíxeles reales (sensor completo si el navegador lo dice; si no, el cuadro de la cámara en vivo)
        const settings = this.track?.getSettings?.() || {};
        const w = this.photoCaps?.imageWidth?.max || settings.width || 0;
        const h = this.photoCaps?.imageHeight?.max || settings.height || 0;
        this.state.mp = Math.round((w * h) / 1e6);
        // flash: linterna (video) o flash de la foto
        const fill = this.photoCaps?.fillLightMode || [];
        this.state.flashSupported = Boolean(this.caps.torch) || fill.includes("flash");
        // zoom
        const zoom = this.caps.zoom;
        this.state.zoomChips = zoom
            ? [0.5, 1, 2, 3, 5].filter((z) => z >= zoom.min - 0.01 && z <= zoom.max + 0.01)
            : [];
        this.state.zoom = Math.max(1, zoom?.min || 1);
        const video = this.videoRef.el;
        if (video) {
            video.srcObject = this.stream;
            await video.play().catch(() => {});
        }
    }

    stopStream() {
        this.stream?.getTracks().forEach((t) => t.stop());
        this.stream = null;
        this.track = null;
    }

    async flip() {
        this.state.facing = this.state.facing === "environment" ? "user" : "environment";
        await this.startStream();
    }

    async applyAdvanced(constraint) {
        try {
            await this.track?.applyConstraints({ advanced: [constraint] });
            return true;
        } catch {
            return false;
        }
    }

    async setZoom(value) {
        const zoom = this.caps.zoom;
        if (!zoom) {
            return;
        }
        const clamped = Math.min(zoom.max, Math.max(zoom.min, value));
        if (await this.applyAdvanced({ zoom: clamped })) {
            this.state.zoom = clamped;
        }
    }

    async cycleFlash() {
        this.state.flash = FLASH_CYCLE[this.state.flash];
        if (this.caps.torch) {
            await this.applyAdvanced({ torch: this.state.flash === "on" });
        }
    }

    // pellizcar con dos dedos para acercar
    onTouchStart(ev) {
        if (ev.touches.length === 2 && this.caps.zoom) {
            this.pinch = { d: this.touchDistance(ev), z: this.state.zoom };
        }
    }

    onTouchMove(ev) {
        if (this.pinch && ev.touches.length === 2) {
            this.setZoom((this.pinch.z * this.touchDistance(ev)) / this.pinch.d);
        }
    }

    onTouchEnd() {
        this.pinch = null;
    }

    touchDistance(ev) {
        const [a, b] = ev.touches;
        return Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY) || 1;
    }

    // ---- captura ----
    async onShutter() {
        if (this.state.mode === "video") {
            return this.toggleRecord();
        }
        return this.takePhoto();
    }

    async takePhoto() {
        if (!this.track || this.state.recording) {
            return;
        }
        let blob = null;
        // 1) Resolución COMPLETA del sensor (Chrome/Android).
        if (window.ImageCapture) {
            try {
                const capture = new window.ImageCapture(this.track);
                const options = {};
                if (this.photoCaps?.imageWidth?.max && this.photoCaps?.imageHeight?.max) {
                    options.imageWidth = this.photoCaps.imageWidth.max;
                    options.imageHeight = this.photoCaps.imageHeight.max;
                }
                if (this.photoCaps?.fillLightMode?.includes("flash")) {
                    options.fillLightMode = { auto: "auto", on: "flash", off: "off" }[this.state.flash];
                }
                blob = await capture.takePhoto(options);
            } catch {
                blob = null;
            }
        }
        // 2) Respaldo: el cuadro de la cámara en vivo a su mayor resolución, calidad 0,97 (sin reducir).
        if (!blob) {
            const video = this.videoRef.el;
            const canvas = document.createElement("canvas");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext("2d").drawImage(video, 0, 0);
            blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.97));
        }
        if (blob) {
            await this.cam.add(this.props.model, this.props.resId, blob, "photo");
            this.state.shot = true;
            setTimeout(() => (this.state.shot = false), 140);
        }
    }

    async toggleRecord() {
        if (this.state.recording) {
            this.stopRecording();
            return;
        }
        if (!this.stream || !window.MediaRecorder) {
            this.notification.add("Este navegador no puede grabar video aquí.", { type: "danger" });
            return;
        }
        const tracks = [...this.stream.getVideoTracks()];
        try {
            const audio = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.audioStream = audio;
            tracks.push(...audio.getAudioTracks());
        } catch {
            this.audioStream = null; // sin micrófono: se graba sin sonido
        }
        const mime = pickVideoMime();
        const options = { videoBitsPerSecond: 12_000_000 }; // alta calidad
        if (mime) {
            options.mimeType = mime;
        }
        const chunks = [];
        this.recorder = new MediaRecorder(new MediaStream(tracks), options);
        this.recorder.ondataavailable = (e) => e.data?.size && chunks.push(e.data);
        this.recorder.onstop = async () => {
            this.audioStream?.getTracks().forEach((t) => t.stop());
            const type = (this.recorder?.mimeType || mime || "video/mp4").split(";")[0];
            const blob = new Blob(chunks, { type });
            if (blob.size) {
                await this.cam.add(this.props.model, this.props.resId, blob, "video");
            }
        };
        this.recorder.start(1000);
        this.state.recording = true;
        this.state.seconds = 0;
        this.recordTimer = setInterval(() => {
            this.state.seconds += 1;
            if (this.state.seconds >= MAX_VIDEO_SECONDS) {
                this.stopRecording();
            }
        }, 1000);
    }

    stopRecording(silent = false) {
        clearInterval(this.recordTimer);
        if (this.recorder && this.recorder.state !== "inactive") {
            this.recorder.stop();
        }
        if (!silent) {
            this.state.recording = false;
        }
    }

    // ---- archivos del carrete / documentos ----
    async onNativeFiles(ev) {
        for (const file of [...ev.target.files]) {
            const { kind, name } = nativeName(file);
            await this.cam.add(this.props.model, this.props.resId, file, kind, name);
        }
        ev.target.value = "";
    }

    // ---- revisar ----
    openReview(id) {
        this.state.review = id;
        this.zoomer?.reset();
    }

    openLast() {
        if (this.lastItem) {
            this.openReview(this.lastItem.id);
        }
    }

    closeReview() {
        this.state.review = null;
        this.zoomer?.reset();
    }

    step(delta) {
        const items = this.items;
        const index = items.findIndex((i) => i.id === this.state.review);
        const next = items[index + delta];
        if (next) {
            this.openReview(next.id);
        }
    }

    async discard() {
        const item = this.reviewItem;
        if (!item) {
            return;
        }
        const items = this.items;
        const index = items.findIndex((i) => i.id === item.id);
        const neighbour = items[index + 1] || items[index - 1];
        const saved = { blob: item.blob, kind: item.kind, name: item.name };
        await this.cam.remove(item.id);
        // se puede deshacer por unos segundos
        this.state.undo = saved;
        clearTimeout(this.undoTimer);
        this.undoTimer = setTimeout(() => (this.state.undo = null), 6000);
        if (neighbour) {
            this.openReview(neighbour.id);
        } else {
            this.closeReview();
        }
    }

    async undoDiscard() {
        const saved = this.state.undo;
        this.state.undo = null;
        if (saved) {
            const item = await this.cam.add(this.props.model, this.props.resId, saved.blob, saved.kind, saved.name);
            this.openReview(item.id);
        }
    }

    // ---- subir / cerrar ----
    async uploadAll() {
        if (!this.items.length) {
            return;
        }
        const { uploaded, failed } = await this.cam.flush(this.props.model, this.props.resId);
        if (uploaded && !failed) {
            this.notification.add(`Se subieron ${uploaded} archivo(s).`, { type: "success" });
            this.props.close();
        } else if (failed) {
            this.notification.add(
                "No hay buena señal: tus fotos y videos quedaron guardados en el teléfono y se subirán solos.",
                { type: "warning" }
            );
        }
    }

    close() {
        const pending = this.items.length;
        if (pending) {
            this.notification.add(
                `${pending} archivo(s) siguen guardados en el teléfono y se subirán solos cuando haya señal.`,
                { type: "info" }
            );
            this.cam.flush(this.props.model, this.props.resId);
        }
        this.props.close();
    }
}


// ---------------------------------------------------------------------------------------------
// Ventana "Cámara / Archivos" que sale al pulsar el clip en celular y tablet
// ---------------------------------------------------------------------------------------------
class DkAttachChoice extends Component {
    static template = "stock_picking_sale_buttons.DkAttachChoice";
    static components = { Dialog };
    static props = {
        close: Function,
        attachmentsCount: { type: Number, optional: true },
        onCamera: Function,
        onFiles: Function,
        onList: Function,
    };

    setup() {
        this.filesRef = useRef("files");
    }

    pickCamera() {
        this.props.close();
        this.props.onCamera();
    }

    pickFiles() {
        this.filesRef.el.click(); // la ventana se queda abierta hasta que llegue el archivo (el input vive aquí)
    }

    pickList() {
        this.props.close();
        this.props.onList();
    }

    async onFiles(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        this.props.close();
        if (files.length) {
            await this.props.onFiles(files);
        }
    }
}

// ---------------------------------------------------------------------------------------------
// El clip del log: archivos originales -> cola guardada en el teléfono -> subida en segundo plano
// ---------------------------------------------------------------------------------------------
FileUploader.props = { ...FileUploader.props, dkRawFiles: { type: Function, optional: true } };

patch(FileUploader.prototype, {
    async onFileChange(ev) {
        if (!this.props.dkRawFiles) {
            return super.onFileChange(...arguments); // cualquier otro FileUploader de Odoo, sin cambios
        }
        const files = [...(ev.target.files || [])];
        if (!files.length) {
            return;
        }
        // Sin base64, sin esperar la subida: los originales pasan directo a la cola.
        ev.target.value = null;
        await this.props.dkRawFiles(files);
    },
});

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.dkCamService = useService("dk_camera");
        this.dkCamState = useState(this.dkCamService.state);
        this.dkDialog = useService("dialog");
    },

    get dkCamPending() {
        const thread = this.state.thread;
        return thread
            ? this.dkCamState.items.filter((i) => i.model === thread.model && i.resId === thread.id).length
            : 0;
    },

    // Archivos elegidos/tomados con el clip.
    async dkQueueFiles(files) {
        const thread = this.state.thread;
        if (!thread?.id) {
            return;
        }
        for (const file of files) {
            const { kind, name } = nativeName(file);
            await this.dkCamService.add(thread.model, thread.id, file, kind, name);
        }
        this.state.isAttachmentBoxOpened = true;
        // En segundo plano: no se espera, para poder tomar la siguiente foto enseguida.
        this.dkCamService.flush(thread.model, thread.id).then(({ uploaded }) => {
            if (uploaded && this.props.hasParentReloadOnAttachmentsChanged) {
                this.reloadParentView?.();
            }
        });
    },

    // El clip: en celulares y tablets pregunta "Cámara o Archivos"; en computadora (mouse) sigue el selector normal.
    get dkIsTouch() {
        return Boolean(window.matchMedia?.("(pointer: coarse)").matches && navigator.mediaDevices?.getUserMedia);
    },

    dkOpenChoice() {
        this.dkDialog.add(DkAttachChoice, {
            attachmentsCount: this.attachments?.length || 0,
            onCamera: () => this.onClickDkCamera(),
            onFiles: (files) => this.dkQueueFiles(files),
            onList: () => {
                this.state.isAttachmentBoxOpened = true;
                if (this.rootRef?.el) {
                    this.rootRef.el.scrollTop = 0;
                }
                this.state.thread.scrollTop = "bottom";
            },
        });
    },

    // Sin archivos todavía: el clip es el selector de Odoo; aquí se cambia por la ventana de elegir.
    async onClickAttachFile(ev) {
        const result = await super.onClickAttachFile(...arguments); // guarda el documento si es nuevo
        if (result === false) {
            return false;
        }
        if (this.dkIsTouch) {
            this.dkOpenChoice();
            return false; // no abrir el selector del sistema
        }
        return result;
    },

    // Con archivos ya subidos, Odoo usa el clip para abrir/cerrar la lista: en celular/tablet preguntamos primero.
    onClickAddAttachments() {
        if (this.dkIsTouch && this.state.thread.canPostMessage) {
            this.dkOpenChoice();
            return;
        }
        return super.onClickAddAttachments(...arguments);
    },

    async onClickDkCamera() {
        if (!this.state.thread.id) {
            // Documento nuevo: se guarda primero, igual que con el botón de adjuntar.
            const saved = await this.props.saveRecord?.();
            if (!saved) {
                return;
            }
        }
        this.dkDialog.add(DkCameraDialog, { model: this.state.thread.model, resId: this.state.thread.id });
    },
});

const waveformPatterns = [
  [22, 38, 54, 30, 76, 46, 64, 28],
  [36, 68, 44, 82, 34, 58, 72, 40],
  [18, 30, 46, 62, 50, 34, 70, 56],
  [60, 42, 78, 36, 88, 50, 70, 44],
  [28, 74, 40, 66, 48, 80, 36, 58]
];

let tracks = [];
let manifestInfo = null;
let activeFilter = "all";
let activeTrack = 0;
let isPlaying = false;
let currentSecond = 0;
let timerId = null;
const audio = new Audio();
audio.preload = "metadata";

const trackList = document.querySelector("#trackList");
const queueList = document.querySelector("#queueList");
const filterTabs = document.querySelector("#filterTabs");
const searchInput = document.querySelector("#searchInput");
const playerTitle = document.querySelector("#playerTitle");
const playerArtist = document.querySelector("#playerArtist");
const playerArt = document.querySelector("#playerArt");
const progressRange = document.querySelector("#progressRange");
const currentTime = document.querySelector("#currentTime");
const durationTime = document.querySelector("#durationTime");
const playerToggle = document.querySelector("[data-player-toggle]");
const featuredPlay = document.querySelector("[data-featured-play]");
const clientIdInput = document.querySelector("#clientIdInput");
const redirectInput = document.querySelector("#redirectInput");
const buildAuthButton = document.querySelector("#buildAuthButton");
const authLink = document.querySelector("#authLink");
const copyAuthCommand = document.querySelector("#copyAuthCommand");
const copyImportCommand = document.querySelector("#copyImportCommand");
const copyRefreshCommand = document.querySelector("#copyRefreshCommand");
const commandPreview = document.querySelector("#commandPreview");
const importStatus = document.querySelector("#importStatus");
const libraryStats = document.querySelector("#libraryStats");
const refreshLibraryButton = document.querySelector("#refreshLibraryButton");
const openUploadButton = document.querySelector("#openUploadButton");
const openUploadTopButton = document.querySelector("#openUploadTopButton");
const closeUploadButton = document.querySelector("#closeUploadButton");
const uploadModal = document.querySelector("#uploadModal");
const uploadForm = document.querySelector("#uploadForm");
const audioFileInput = document.querySelector("#audioFileInput");
const uploadTitleInput = document.querySelector("#uploadTitleInput");
const uploadStatus = document.querySelector("#uploadStatus");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function formatCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return value || "0";
  if (number >= 1000000) return `${(number / 1000000).toFixed(1)}M`;
  if (number >= 1000) return `${(number / 1000).toFixed(1)}K`;
  return number.toLocaleString();
}

function normalizeTrack(track, index) {
  return {
    id: track.id || track.soundcloudId || `${index}`,
    title: track.title || `Untitled ${index + 1}`,
    artist: track.artist || "Musicloud",
    genre: (track.genre || "cloudcast").toLowerCase(),
    duration: Number(track.duration) || 0,
    plays: track.plays || 0,
    comments: Number(track.comments) || 0,
    likes: Number(track.likes) || 0,
    cover: track.cover || `cover-${["one", "two", "three", "four", "five"][index % 5]}`,
    artwork: track.artwork || "",
    src: track.streamUrl || track.src || "",
    originalSrc: track.src || "",
    downloadUrl: track.downloadUrl || track.src || "",
    soundcloudUrl: track.soundcloudUrl || "",
    source: track.source || "",
    pattern: track.pattern || waveformPatterns[index % waveformPatterns.length]
  };
}

function makeRandomString(byteLength = 32) {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function makePkceChallenge(verifier) {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

function showCommand(text) {
  commandPreview.textContent = text;
}

function getAuthCommand() {
  return "start_musicloud_import.cmd";
}

function getImportCommand() {
  return "py start_musicloud_import.py";
}

function setUploadOpen(isOpen) {
  if (!uploadModal) return;
  uploadModal.hidden = !isOpen;
  if (isOpen) {
    window.setTimeout(() => audioFileInput?.focus(), 0);
  }
}

function setUploadStatus(message) {
  if (uploadStatus) {
    uploadStatus.textContent = message;
  }
}

function inferTitleFromFile(file) {
  if (!file || !file.name) return "";
  return file.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ").trim();
}

async function readApiResponse(response, action) {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json().catch(() => ({})) : {};

  if (response.ok && isJson) {
    return payload;
  }

  if (response.status === 413) {
    throw new Error("The server rejected this upload as too large. On tubamobile.com, nginx needs a larger client_max_body_size and /api must proxy to Musicloud API.");
  }

  if (!isJson) {
    throw new Error(`Musicloud API is not reachable for ${action}. The server is returning the website page instead of API JSON.`);
  }

  throw new Error(payload.error || `${action} failed with HTTP ${response.status}.`);
}

function getFilteredTracks() {
  const query = searchInput.value.trim().toLowerCase();
  return tracks.filter((track) => {
    const matchesFilter = activeFilter === "all" || track.genre === activeFilter;
    const matchesSearch = `${track.title} ${track.artist} ${track.genre}`.toLowerCase().includes(query);
    return matchesFilter && matchesSearch;
  });
}

function renderFilters() {
  const genres = Array.from(new Set(tracks.map((track) => track.genre).filter(Boolean))).sort();
  if (activeFilter !== "all" && !genres.includes(activeFilter)) {
    activeFilter = "all";
  }

  filterTabs.innerHTML = [
    `<button class="tab ${activeFilter === "all" ? "active" : ""}" type="button" data-filter="all">All</button>`,
    ...genres.map((genre) => (
      `<button class="tab ${activeFilter === genre ? "active" : ""}" type="button" data-filter="${escapeHtml(genre)}">${escapeHtml(genre)}</button>`
    ))
  ].join("");
}

function getTrackDuration(track) {
  return track.duration || Math.round(audio.duration) || 180;
}

function getCoverMarkup(track, className = "cover") {
  if (track.artwork) {
    return `<img class="${className}" src="${escapeHtml(track.artwork)}" alt="" loading="lazy">`;
  }
  return `<div class="${className} ${track.cover}" aria-hidden="true"></div>`;
}

function makeWaveform(track, trackIndex) {
  const duration = getTrackDuration(track);
  const bars = Array.from({ length: 64 }, (_, index) => {
    const base = track.pattern[index % track.pattern.length];
    const variation = (index * 11 + track.title.length * 3) % 24;
    const height = Math.min(92, base + variation);
    const playedClass = trackIndex === activeTrack && index / 64 <= currentSecond / duration ? " played" : "";
    return `<span class="bar${playedClass}" style="height:${height}%"></span>`;
  }).join("");

  return `<button class="waveform" type="button" aria-label="Play ${escapeHtml(track.title)}" data-track="${trackIndex}">${bars}</button>`;
}

function renderTracks() {
  const filtered = getFilteredTracks();
  trackList.innerHTML = filtered.length
    ? filtered.map((track) => {
        const trackIndex = tracks.indexOf(track);
        const isActive = trackIndex === activeTrack ? " active" : "";
        const duration = getTrackDuration(track);
        return `
          <article class="track-card${isActive}">
            ${getCoverMarkup(track)}
            <div class="track-main">
              <div class="track-top">
                <div>
                  <p class="track-artist">${escapeHtml(track.artist)}</p>
                  <h3 class="track-title">${escapeHtml(track.title)}</h3>
                </div>
                <div class="track-actions">
                  <button class="track-action" type="button" data-track="${trackIndex}" data-play>
                    <span data-lucide="${trackIndex === activeTrack && isPlaying ? "pause" : "play"}"></span>
                    ${trackIndex === activeTrack && isPlaying ? "Pause" : "Play"}
                  </button>
                  <button class="track-action" type="button" data-like>
                    <span data-lucide="heart"></span>
                    ${formatCount(track.likes)}
                  </button>
                  ${track.downloadUrl ? `
                    <a class="track-action" href="${escapeHtml(track.downloadUrl)}" download>
                      <span data-lucide="download"></span>
                      Download
                    </a>
                  ` : ""}
                  <button class="track-action danger" type="button" data-delete-track="${trackIndex}">
                    <span data-lucide="trash-2"></span>
                    Delete
                  </button>
                </div>
              </div>
              ${makeWaveform(track, trackIndex)}
              <div class="track-meta">
                <span>${formatCount(track.plays)} plays</span>
                <span>${formatCount(track.comments)} comments</span>
                <span>${formatTime(duration)}</span>
                <span>${escapeHtml(track.genre)}</span>
              </div>
            </div>
          </article>
        `;
      }).join("")
    : `<div class="panel"><h2>No imported tracks found</h2><p>Run the SoundCloud importer or clear the current search/filter.</p></div>`;

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderLibraryStats() {
  if (!libraryStats) return;
  const skipped = manifestInfo ? Number(manifestInfo.skipped || 0) : 0;
  const downloaded = manifestInfo ? Number(manifestInfo.downloaded || tracks.length) : tracks.length;
  const genres = new Set(tracks.map((track) => track.genre).filter(Boolean));
  const totalSeconds = tracks.reduce((sum, track) => sum + getTrackDuration(track), 0);
  const totalHours = totalSeconds / 3600;

  libraryStats.innerHTML = tracks.length
    ? `
      <article class="artist-row">
        <span class="avatar avatar-gradient-two"></span>
        <div>
          <h3>${formatCount(downloaded)} tracks</h3>
          <p>${totalHours.toFixed(1)} hours loaded</p>
        </div>
      </article>
      <article class="artist-row">
        <span class="avatar avatar-gradient-three"></span>
        <div>
          <h3>${genres.size || 1} genres</h3>
          <p>${skipped} skipped by SoundCloud</p>
        </div>
      </article>
      <article class="artist-row">
        <span class="avatar avatar-gradient-four"></span>
        <div>
          <h3>Sazran</h3>
          <p>Imported SoundCloud archive</p>
        </div>
      </article>
    `
    : `<p class="import-status">No imported tracks loaded yet.</p>`;
}

function renderQueue() {
  queueList.innerHTML = tracks.length ? tracks.slice(0, 4).map((track, index) => `
    <li>
      <span class="queue-index">${index + 1}</span>
      <div>
        <h3>${escapeHtml(track.title)}</h3>
        <p>${escapeHtml(track.artist)}</p>
      </div>
    </li>
  `).join("") : `<li><span class="queue-index">0</span><div><h3>No tracks loaded</h3><p>Run the importer</p></div></li>`;
}

function syncPlayer() {
  const track = tracks[activeTrack];
  if (!track) {
    playerTitle.textContent = "No track selected";
    playerArtist.textContent = "Musicloud";
    playerArt.className = "mini-cover cover-one";
    playerArt.style.backgroundImage = "";
    progressRange.value = "0";
    currentTime.textContent = "0:00";
    durationTime.textContent = "0:00";
    playerToggle.innerHTML = `<span data-lucide="play"></span>`;
    if (window.lucide) {
      window.lucide.createIcons();
    }
    return;
  }
  playerTitle.textContent = track.title;
  playerArtist.textContent = track.artist;
  if (track.artwork) {
    playerArt.className = "mini-cover";
    playerArt.style.backgroundImage = `url("${track.artwork}")`;
  } else {
    playerArt.className = `mini-cover ${track.cover}`;
    playerArt.style.backgroundImage = "";
  }
  const duration = getTrackDuration(track);
  progressRange.value = String((currentSecond / duration) * 100);
  currentTime.textContent = formatTime(currentSecond);
  durationTime.textContent = formatTime(duration);
  playerToggle.innerHTML = `<span data-lucide="${isPlaying ? "pause" : "play"}"></span>`;
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function loadAudioForActiveTrack(startAt = 0) {
  const track = tracks[activeTrack];
  if (!track || !track.src) return false;
  const currentSrc = audio.getAttribute("data-track-src");
  if (currentSrc !== track.src) {
    audio.src = track.src;
    audio.setAttribute("data-track-src", track.src);
  }
  try {
    audio.currentTime = startAt;
  } catch {
    audio.addEventListener("loadedmetadata", () => {
      audio.currentTime = startAt;
    }, { once: true });
  }
  return true;
}

function playTrack(trackIndex, startAt = 0) {
  if (!tracks.length || !tracks[trackIndex]) return;
  activeTrack = trackIndex;
  currentSecond = startAt;
  isPlaying = true;
  if (loadAudioForActiveTrack(startAt)) {
    window.clearInterval(timerId);
    audio.play().catch(() => {
      isPlaying = false;
      syncPlayer();
      renderTracks();
    });
  } else {
    startTimer();
  }
  syncPlayer();
  renderTracks();
}

function startTimer() {
  window.clearInterval(timerId);
  timerId = window.setInterval(() => {
    if (!isPlaying || !tracks.length) return;
    const track = tracks[activeTrack];
    currentSecond += 1;
    if (currentSecond >= getTrackDuration(track)) {
      activeTrack = (activeTrack + 1) % tracks.length;
      currentSecond = 0;
    }
    syncPlayer();
    renderTracks();
  }, 1000);
}

function togglePlay() {
  if (!tracks.length) return;
  isPlaying = !isPlaying;
  if (isPlaying) {
    if (loadAudioForActiveTrack(currentSecond)) {
      window.clearInterval(timerId);
      audio.play().catch(() => {
        isPlaying = false;
        syncPlayer();
        renderTracks();
      });
    } else {
      startTimer();
    }
  } else {
    audio.pause();
  }
  syncPlayer();
  renderTracks();
}

document.addEventListener("click", (event) => {
  const playButton = event.target.closest("[data-play]");
  const waveform = event.target.closest(".waveform");
  const likeButton = event.target.closest("[data-like]");
  const filterButton = event.target.closest("[data-filter]");
  const deleteButton = event.target.closest("[data-delete-track]");

  if (playButton) {
    const trackIndex = Number(playButton.dataset.track);
    if (trackIndex === activeTrack) {
      togglePlay();
    } else {
      playTrack(trackIndex);
    }
  }

  if (waveform) {
    const trackIndex = Number(waveform.dataset.track);
    const rect = waveform.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    playTrack(trackIndex, Math.floor(getTrackDuration(tracks[trackIndex]) * ratio));
  }

  if (likeButton) {
    likeButton.classList.toggle("liked");
  }

  if (filterButton) {
    activeFilter = filterButton.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((button) => {
      button.classList.toggle("active", button === filterButton);
    });
    renderTracks();
  }

  if (deleteButton) {
    const trackIndex = Number(deleteButton.dataset.deleteTrack);
    const track = tracks[trackIndex];
    if (!track) return;
    const confirmed = window.confirm(`Delete "${track.title}" from Musicloud?\n\nThis removes it from the site and deletes its local audio/artwork files. This cannot be undone.`);
    if (!confirmed) return;

    fetch(`/api/tracks/${encodeURIComponent(track.id)}`, { method: "DELETE" })
      .then(async (response) => {
        return readApiResponse(response, "Delete");
      })
      .then(async () => {
        await loadExportedTracks();
        activeTrack = Math.min(activeTrack, Math.max(0, tracks.length - 1));
        renderFilters();
        renderQueue();
        renderLibraryStats();
        renderTracks();
        syncPlayer();
      })
      .catch((error) => {
        window.alert(error.message);
      });
  }
});

searchInput.addEventListener("input", renderTracks);

playerToggle.addEventListener("click", togglePlay);
featuredPlay.addEventListener("click", () => {
  if (tracks.length) playTrack(0);
});

document.querySelector("[data-prev]").addEventListener("click", () => {
  if (!tracks.length) return;
  activeTrack = (activeTrack - 1 + tracks.length) % tracks.length;
  currentSecond = 0;
  if (isPlaying) playTrack(activeTrack);
  syncPlayer();
  renderTracks();
});

document.querySelector("[data-next]").addEventListener("click", () => {
  if (!tracks.length) return;
  activeTrack = (activeTrack + 1) % tracks.length;
  currentSecond = 0;
  if (isPlaying) playTrack(activeTrack);
  syncPlayer();
  renderTracks();
});

progressRange.addEventListener("input", () => {
  const track = tracks[activeTrack];
  if (!track) return;
  currentSecond = Math.floor((Number(progressRange.value) / 100) * getTrackDuration(track));
  if (track.src && audio.src) {
    audio.currentTime = currentSecond;
  }
  syncPlayer();
  renderTracks();
});

openUploadButton?.addEventListener("click", () => setUploadOpen(true));
openUploadTopButton?.addEventListener("click", () => setUploadOpen(true));
closeUploadButton?.addEventListener("click", () => setUploadOpen(false));

uploadModal?.addEventListener("click", (event) => {
  if (event.target === uploadModal) {
    setUploadOpen(false);
  }
});

audioFileInput?.addEventListener("change", () => {
  const file = audioFileInput.files?.[0];
  if (file && uploadTitleInput && !uploadTitleInput.value.trim()) {
    uploadTitleInput.value = inferTitleFromFile(file);
  }
});

uploadForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!audioFileInput?.files?.length) {
    setUploadStatus("Choose an audio file first.");
    return;
  }

  const formData = new FormData(uploadForm);
  setUploadStatus("Uploading...");

  try {
    const response = await fetch("/api/tracks", {
      method: "POST",
      body: formData
    });
    const payload = await readApiResponse(response, "Upload");
    uploadForm.reset();
    setUploadStatus(`Uploaded ${payload.title || "track"}.`);
    await loadExportedTracks();
    renderFilters();
    renderQueue();
    renderLibraryStats();
    renderTracks();
    syncPlayer();
  } catch (error) {
    setUploadStatus(error.message);
  }
});

buildAuthButton.addEventListener("click", async () => {
  const clientId = clientIdInput.value.trim();
  const redirectUri = redirectInput.value.trim();
  if (!clientId || !redirectUri) {
    showCommand("Add your SoundCloud client ID and redirect URL first.");
    return;
  }

  const verifier = makeRandomString(32);
  const challenge = await makePkceChallenge(verifier);
  const state = makeRandomString(18);
  sessionStorage.setItem("soundcloud_pkce_verifier", verifier);
  sessionStorage.setItem("soundcloud_oauth_state", state);

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    code_challenge: challenge,
    code_challenge_method: "S256",
    state
  });

  authLink.href = `https://secure.soundcloud.com/authorize?${params.toString()}`;
  authLink.classList.add("ready");
  showCommand(`You can test the auth URL here, but the recommended path is the local helper because it catches the OAuth callback and downloads tracks:\n\n${getAuthCommand()}`);
});

copyAuthCommand.addEventListener("click", async () => {
  const command = getAuthCommand();
  showCommand(command);
  await copyText(command);
});

copyImportCommand.addEventListener("click", async () => {
  const command = getImportCommand();
  showCommand(command);
  await copyText(command);
});

copyRefreshCommand.addEventListener("click", async () => {
  const command = window.location.origin + "/";
  showCommand(command);
  await copyText(command);
});

refreshLibraryButton.addEventListener("click", async () => {
  await loadExportedTracks();
  renderFilters();
  renderQueue();
  renderLibraryStats();
  renderTracks();
  syncPlayer();
});

audio.addEventListener("loadedmetadata", () => {
  if (!tracks[activeTrack]) return;
  tracks[activeTrack].duration = Math.round(audio.duration);
  syncPlayer();
  renderLibraryStats();
  renderTracks();
});

audio.addEventListener("timeupdate", () => {
  currentSecond = Math.floor(audio.currentTime);
  syncPlayer();
  renderTracks();
});

audio.addEventListener("ended", () => {
  if (!tracks.length) return;
  activeTrack = (activeTrack + 1) % tracks.length;
  currentSecond = 0;
  if (isPlaying) {
    playTrack(activeTrack);
  }
});

async function loadExportedTracks() {
  const sources = ["api/tracks", "data/tracks.json"];
  for (const source of sources) {
    try {
      const response = await fetch(source, { cache: "no-store" });
      if (!response.ok) continue;
      const manifest = await response.json();
      if (!Array.isArray(manifest.tracks)) continue;
      manifestInfo = manifest;
      tracks = manifest.tracks.map(normalizeTrack);
      activeTrack = 0;
      currentSecond = 0;
      if (importStatus) {
        const mode = source.startsWith("api/") ? "API" : "manifest";
        importStatus.textContent = `${tracks.length} tracks loaded from ${mode}.`;
      }
      return;
    } catch {
      continue;
    }
  }

  tracks = [];
  manifestInfo = null;
}

async function init() {
  await loadExportedTracks();
  renderFilters();
  renderQueue();
  renderLibraryStats();
  renderTracks();
  syncPlayer();
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

init();

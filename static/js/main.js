document.addEventListener('DOMContentLoaded', () => {
  const video          = document.getElementById('video');
  const scanStatus     = document.getElementById('scanStatus');
  const scanIcon       = document.getElementById('scanIcon');
  const scanText       = document.getElementById('scanText');
  const scanSub        = document.getElementById('scanSub');
  const studentDetails = document.getElementById('studentDetails');
  const studentMeta    = document.getElementById('studentMeta');
  const marksTable     = document.getElementById('marksTable');

  if (!video) return;

  // ── Cooldown: prevent re-marking the same student within 1 hour ───────────
  const cooldowns = new Map();    // name → timestamp of last mark
  const COOLDOWN_MS = 60 * 60 * 1000; // 1 hour — matches ATTENDANCE_COOLDOWN_MINUTES in app.py

  // ── Processing lock: skip a tick if previous request is still in-flight ──
  let processing = false;

  // ── Helper: set scan-status indicator state ──────────────────────────────
  const STATES = {
    scanning: {
      icon: 'fas fa-circle-notch fa-spin',
      text: 'Scanning…',
      sub:  'Looking for a face',
      cls:  'scanning'
    },
    matching: {
      icon: 'fas fa-circle-notch fa-spin',
      text: 'Matching…',
      sub:  'Comparing with database',
      cls:  'scanning'
    },
    recognized: (name, count, subject) => ({
      icon: 'fas fa-check-circle',
      text: `✅ Welcome, ${name}!`,
      sub:  subject
        ? `Attendance recorded for ${subject}  ·  Total: ${count}`
        : `Attendance recorded  ·  Total: ${count}`,
      cls:  'recognized'
    }),
    invalid: {
      icon: 'fas fa-times-circle',
      text: '❌ Invalid / Unrecognized Face',
      sub:  'Please look directly at the camera',
      cls:  'invalid'
    },
    cooldown: (name, secsLeft) => ({
      icon: 'fas fa-clock',
      text: `✅ ${name} — Already marked`,
      sub:  `Next mark allowed in ${Math.ceil(secsLeft/60)}m`,
      cls:  'cooldown'
    }),
    timelimit: (name, secsLeft) => ({
      icon: 'fas fa-hourglass-half',
      text: `⏳ ${name} — Please wait`,
      sub:  `Next mark allowed in ${Math.ceil(secsLeft/60)}m`,
      cls:  'cooldown'
    }),
    noface: {
      icon: 'fas fa-user-slash',
      text: 'No face detected',
      sub:  'Move closer and face the camera',
      cls:  'invalid'
    },
    ready: {
      icon: 'fas fa-camera',
      text: 'Auto-scan active',
      sub:  'Position your face in the frame',
      cls:  'scanning'
    }
  };

  function setStatus(state) {
    if (!scanStatus) return;
    const s = typeof state === 'function' ? state() : state;
    scanStatus.className = `scan-status ${s.cls}`;
    if (scanIcon) scanIcon.className = s.icon;
    if (scanText) scanText.textContent = s.text;
    if (scanSub)  scanSub.textContent  = s.sub;
  }

  // ── Render student details panel (QR code version) ───────────────────────
  const studentNameEl = document.getElementById('studentName');
  const qrCodeBox     = document.getElementById('qrCodeBox');
  let   lastQRName    = null;   // avoid regenerating the same QR twice

  const clearStudentDetails = () => {
    if (studentDetails) studentDetails.classList.add('d-none');
    if (studentMeta)    studentMeta.textContent = '';
    if (marksTable)     marksTable.innerHTML = '';
    lastQRName = null;
  };

  const renderStudentDetails = (data) => {
    if (!studentDetails) return;
    const student    = data.student    || {};
    const attendance = data.attendance || {};
    const name       = student.name    || data.name || '';

    // Update name line
    if (studentNameEl) studentNameEl.textContent = name;

    const attText = attendance.last_seen
      ? `${attendance.count} class(es)  ·  ${attendance.last_seen.date}`
      : `${attendance.count || 0} class(es) attended`;
    if (studentMeta) studentMeta.textContent = attText;

    // Generate QR code (only if student changed)
    if (qrCodeBox && name && name !== lastQRName) {
      lastQRName = name;
      qrCodeBox.innerHTML = '';
      const profileUrl = `${window.location.origin}/profile/${encodeURIComponent(name)}`;
      try {
        new QRCode(qrCodeBox, {
          text:         profileUrl,
          width:        160,
          height:       160,
          colorDark:    '#1e1b4b',
          colorLight:   '#ffffff',
          correctLevel: QRCode.CorrectLevel.M,
        });
      } catch (e) {
        qrCodeBox.textContent = profileUrl;
      }
    }

    studentDetails.classList.remove('d-none');
  };

  // ── Class Schedule Banner ─────────────────────────────────────────────────
  const classBanner = document.getElementById('classBanner');
  const bannerSubject = document.getElementById('bannerSubject');
  const bannerRoom    = document.getElementById('bannerRoom');
  const bannerTime    = document.getElementById('bannerTime');
  const bannerMins    = document.getElementById('bannerMins');

  async function refreshClassBanner() {
    if (!classBanner) return;
    try {
      const resp = await fetch('/api/current_class');
      const data = await resp.json();
      if (data.active) {
        if (bannerSubject) bannerSubject.textContent = data.subject;
        if (bannerRoom)    bannerRoom.textContent    = data.room;
        if (bannerTime)    bannerTime.textContent    = `${data.start} – ${data.end}`;
        if (bannerMins)    bannerMins.textContent    = `${data.mins_remaining} min left`;
        classBanner.classList.remove('d-none');
        classBanner.classList.add('class-active');
      } else {
        classBanner.classList.add('d-none');
        classBanner.classList.remove('class-active');
      }
    } catch (e) {
      // silently ignore
    }
  }

  // Poll every 60 seconds to update the banner
  refreshClassBanner();
  setInterval(refreshClassBanner, 60 * 1000);

  // ── Camera startup ────────────────────────────────────────────────────────
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: false
      });
      video.srcObject = stream;
      video.onloadedmetadata = () => {
        setStatus(STATES.ready);
        startAutoScan();
      };
    } catch (err) {
      const isLocal = ['localhost', '127.0.0.1'].includes(location.hostname);
      const hint = isLocal
        ? 'Please allow camera access in your browser settings.'
        : 'Camera requires HTTPS or localhost.';
      if (scanText) scanText.textContent = `Camera error: ${err.message}`;
      if (scanSub)  scanSub.textContent  = hint;
      if (scanStatus) scanStatus.className = 'scan-status invalid';
    }
  };

  // ── Capture a JPEG frame from the video element ───────────────────────────
  const captureFrame = () => {
    const canvas = document.createElement('canvas');
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
  };

  // ── One scan tick ─────────────────────────────────────────────────────────
  const doScan = async () => {
    if (processing) return;
    if (!video.srcObject || video.readyState < 2) return;

    processing = true;
    setStatus(STATES.scanning);

    let image;
    try {
      image = captureFrame();
    } catch (_) {
      processing = false;
      setStatus(STATES.ready);
      return;
    }

    setStatus(STATES.matching);

    try {
      const resp = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image })
      });
      const data = await resp.json();

      if (data.error === 'No face found' || data.error === 'No registered students') {
        setStatus(STATES.noface);
        clearStudentDetails();
      } else if (data.match) {
        const name = data.name;
        const now  = Date.now();
        const subj = data.current_subject || null;

        if (data.cooldown_remaining && data.cooldown_remaining > 0) {
          // Backend time-limit active — show countdown from server's remaining seconds
          setStatus(STATES.timelimit(name, data.cooldown_remaining));
          // Record local cooldown so next ticks skip the server until backend cooldown expires
          cooldowns.set(name, now - (COOLDOWN_MS - data.cooldown_remaining * 1000));
          if (data.student) renderStudentDetails(data);
        } else if (cooldowns.has(name) && (now - cooldowns.get(name)) < COOLDOWN_MS) {
          // Local JS cooldown (avoids spamming server during the wait window)
          const secsLeft = Math.ceil((COOLDOWN_MS - (now - cooldowns.get(name))) / 1000);
          setStatus(STATES.cooldown(name, secsLeft));
        } else {
          cooldowns.set(name, now);
          const count = data.attendance ? data.attendance.count : '—';
          setStatus(STATES.recognized(name, count, subj));
          renderStudentDetails(data);
        }
      } else {
        setStatus(STATES.invalid);
        clearStudentDetails();
      }
    } catch (err) {
      console.warn('[AutoScan] fetch error:', err);
      setStatus(STATES.ready);
    } finally {
      processing = false;
    }
  };

  // ── Auto-scan loop: fires every 1500 ms ───────────────────────────────────
  let scanInterval = null;
  const startAutoScan = () => {
    if (scanInterval) clearInterval(scanInterval);
    scanInterval = setInterval(doScan, 1500);
  };

  // ── Boot ──────────────────────────────────────────────────────────────────
  startCamera();
});

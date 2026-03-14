document.addEventListener('DOMContentLoaded', () => {
  const addForm = document.getElementById('addForm');
  const addResult = document.getElementById('addResult');
  const adminMarksTable = document.getElementById('adminMarksTable');
  const marksStudentSelect = document.getElementById('marksStudentSelect');
  const syncMarksButton = document.getElementById('syncMarks');
  const syncStatus = document.getElementById('syncStatus');
  const adminVideo = document.getElementById('adminVideo');
  const capturePhoto = document.getElementById('capturePhoto');
  const capturedPreview = document.getElementById('capturedPreview');
  const captureHint = document.getElementById('captureHint');
  let capturedBlob = null;

  const startAdminCamera = async () => {
    if (!adminVideo) {
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
        audio: false
      });
      adminVideo.srcObject = stream;
      if (captureHint) {
        captureHint.textContent = 'Camera ready. Capture a photo to attach.';
      }
    } catch (error) {
      if (captureHint) {
        const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
        const hint = isLocalhost
          ? 'Please allow camera access in your browser.'
          : 'Camera access requires HTTPS or localhost.';
        captureHint.textContent = `Camera error: ${error.message}. ${hint}`;
      }
    }
  };

  const captureFromVideo = () => {
    if (!adminVideo) {
      return;
    }
    const canvas = document.createElement('canvas');
    canvas.width = adminVideo.videoWidth || 640;
    canvas.height = adminVideo.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(adminVideo, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        return;
      }
      capturedBlob = blob;
      if (capturedPreview) {
        capturedPreview.src = URL.createObjectURL(blob);
        capturedPreview.classList.add('is-ready');
      }
      if (captureHint) {
        captureHint.textContent = 'Captured photo will be uploaded on submit.';
      }
    }, 'image/jpeg', 0.9);
  };

  if (capturePhoto) {
    capturePhoto.addEventListener('click', captureFromVideo);
  }

  if (addForm) {
    addForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      addResult.textContent = 'Uploading...';

      try {
        const formData = new FormData(addForm);
        const fileInput = addForm.querySelector('input[type="file"][name="image"]');
        if (capturedBlob && fileInput && fileInput.files.length === 0) {
          const file = new File([capturedBlob], 'capture.jpg', { type: 'image/jpeg' });
          formData.set('image', file);
        }

        const response = await fetch('/api/admin/add_student', {
          method: 'POST',
          body: formData
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to add student.');
        }

        addResult.textContent = 'Student added successfully.';
        addResult.className = 'text-success';
        window.location.reload();
      } catch (error) {
        addResult.textContent = error.message;
        addResult.className = 'text-danger';
      }
    });
  }

  const renderMarksTable = (marks) => {
    if (!adminMarksTable) return;
    if (!marks || !marks.length) {
      adminMarksTable.innerHTML = '<tr><td colspan="6" class="text-center text-white-60 py-3">No marks recorded yet.</td></tr>';
      return;
    }
    adminMarksTable.innerHTML = marks.map(mark => {
      const pct = mark.max_score > 0 ? ((mark.score / mark.max_score) * 100).toFixed(1) : '–';
      const style = pct !== '–' && parseFloat(pct) < 40
        ? 'color:var(--danger);font-weight:700;'
        : 'color:var(--success);';
      return `<tr>
        <td>${mark.subject}</td>
        <td>${mark.exam_type}</td>
        <td>${mark.term}</td>
        <td>${mark.score}</td>
        <td>${mark.max_score}</td>
        <td style="${style}">${pct}%</td>
      </tr>`;
    }).join('');
  };

  const loadStudentDetails = async (name) => {
    if (!name) {
      renderMarksTable([]);
      return;
    }
    const response = await fetch(`/api/admin/student_details?name=${encodeURIComponent(name)}`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Failed to load student details.');
    }
    renderMarksTable(data.marks || []);
  };

  const syncMarks = async (shouldReload) => {
    if (syncStatus) {
      syncStatus.textContent = 'Syncing from sheet...';
    }
    try {
      const response = await fetch('/api/admin/sync_marks');
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to sync marks.');
      }
      if (syncStatus) {
        syncStatus.textContent = `Synced ${data.students} students and ${data.marks} marks.`;
      }
      if (shouldReload) {
        window.location.reload();
      }
    } catch (error) {
      if (syncStatus) {
        syncStatus.textContent = error.message;
      }
    }
  };

  if (marksStudentSelect) {
    marksStudentSelect.addEventListener('change', async (event) => {
      try {
        await loadStudentDetails(event.target.value);
      } catch (error) {
        if (syncStatus) {
          syncStatus.textContent = error.message;
        }
      }
    });
  }

  if (syncMarksButton) {
    syncMarksButton.addEventListener('click', () => syncMarks(true));
  }

  document.body.addEventListener('click', async (event) => {
    const removeButton = event.target.closest('button.remove');
    const sendButton = event.target.closest('button.send-marks');

    if (removeButton) {
      const name = removeButton.dataset.name;
      if (!name) {
        return;
      }

      removeButton.disabled = true;
      try {
        const response = await fetch('/api/admin/remove_student', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ name })
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to remove student.');
        }

        window.location.reload();
      } catch (error) {
        removeButton.disabled = false;
        alert(error.message);
      }
      return;
    }

    if (sendButton) {
      const name = sendButton.dataset.name;
      if (!name) {
        return;
      }
      sendButton.disabled = true;
      try {
        const response = await fetch('/api/admin/send_marks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ name })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || 'Failed to send marks.');
        }
        alert('Marks email sent.');
      } catch (error) {
        alert(error.message);
      } finally {
        sendButton.disabled = false;
      }
    }
  });

  // ── Performance Alerts ────────────────────────────────────────────
  const checkAlertsBtn = document.getElementById('checkAlertsBtn');
  const alertStatus = document.getElementById('alertStatus');
  const performanceTable = document.getElementById('performanceTable');
  const alertCountEl = document.getElementById('alertCount');

  const renderPerformanceTable = (results, threshold) => {
    if (!performanceTable) return;
    if (!results || !results.length) {
      performanceTable.innerHTML = '<tr><td colspan="5" class="text-center text-white-60 py-3">No students found.</td></tr>';
      return;
    }
    const belowCount = results.filter(r => r.below_threshold).length;
    if (alertCountEl) alertCountEl.textContent = belowCount;

    performanceTable.innerHTML = results.map(r => {
      const marksPct = r.marks_percentage !== null ? r.marks_percentage + '%' : '–';
      const attPct = r.attendance_percentage !== null ? r.attendance_percentage + '%' : '–';
      const marksClass = (r.marks_percentage !== null && r.marks_percentage < threshold) ? 'text-danger fw-bold' : 'text-white-80';
      const attClass = (r.attendance_percentage !== null && r.attendance_percentage < threshold) ? 'text-danger fw-bold' : 'text-white-80';
      const statusBadge = r.below_threshold
        ? '<span class="badge" style="background:rgba(255,107,53,0.25);color:#ff6b35;">⚠ Below Threshold</span>'
        : '<span class="badge bg-success bg-opacity-25 text-success">✓ OK</span>';
      const alertBadge = r.alert_sent
        ? '<span class="badge bg-success bg-opacity-25 text-success"><i class="fas fa-check me-1"></i>Sent</span>'
        : '<span class="badge" style="background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.5);">–</span>';
      return `<tr>
        <td><strong class="student-name-dark">${r.name}</strong></td>
        <td class="${marksClass}">${marksPct}</td>
        <td class="${attClass}">${attPct}</td>
        <td>${statusBadge}</td>
        <td>${alertBadge}</td>
      </tr>`;
    }).join('');
  };

  const loadPerformanceSummary = async () => {
    try {
      const resp = await fetch('/api/admin/performance_summary');
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Failed to load performance data.');
      renderPerformanceTable(data.students.map(s => ({ ...s, alert_sent: false })), data.threshold);
    } catch (err) {
      console.warn('Performance summary load failed:', err.message);
    }
  };

  const checkAlerts = async () => {
    if (!checkAlertsBtn) return;
    checkAlertsBtn.disabled = true;
    if (alertStatus) alertStatus.textContent = 'Checking performance…';
    try {
      const resp = await fetch('/api/admin/check_alerts', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || 'Failed to check alerts.');
      if (alertStatus) {
        alertStatus.textContent = `Checked ${data.checked} student(s). ${data.alerts_sent} alert(s) sent.`;
      }
      renderPerformanceTable(data.results, 40);
    } catch (err) {
      if (alertStatus) alertStatus.textContent = err.message;
    } finally {
      checkAlertsBtn.disabled = false;
    }
  };

  if (checkAlertsBtn) checkAlertsBtn.addEventListener('click', checkAlerts);

  // Load performance summary on page load (read-only, no emails)
  loadPerformanceSummary();

  // ── Today's Summary (Present / Absent) ────────────────────────────
  const todayCountEl    = document.getElementById('todayCount');
  const todayRateEl     = document.getElementById('todayRate');
  const presentGrid     = document.getElementById('presentTodayGrid');
  const presentDateEl   = document.getElementById('presentTodayDate');
  const presentMetaEl   = document.getElementById('presentTodayMeta');

  const loadTodaySummary = async () => {
    try {
      const resp = await fetch('/api/admin/today_summary');
      const data = await resp.json();
      if (!resp.ok) return;

      // Update stat cards
      if (todayCountEl) todayCountEl.textContent = data.present_count;
      if (todayRateEl) {
        const rate = data.total > 0 ? Math.round((data.present_count / data.total) * 100) : 0;
        todayRateEl.textContent = rate + '%';
      }
      if (presentDateEl) presentDateEl.textContent = data.today;
      if (presentMetaEl) presentMetaEl.textContent = `${data.present_count} present · ${data.absent.length} absent`;

      // Render presence grid
      if (!presentGrid) return;
      if (data.total === 0) {
        presentGrid.innerHTML = '<span class="text-white-60">No students registered yet.</span>';
        return;
      }
      const chips = [
        ...data.present.map(name =>
          `<span class="presence-chip present"><i class="fas fa-check-circle me-1"></i>${name}</span>`),
        ...data.absent.map(name =>
          `<span class="presence-chip absent"><i class="fas fa-times-circle me-1"></i>${name}</span>`),
      ];
      presentGrid.innerHTML = chips.join('');
    } catch (e) {
      console.warn('Today summary failed:', e);
    }
  };

  loadTodaySummary();
  setInterval(loadTodaySummary, 30 * 1000);  // refresh every 30 s

  // ── Date Filter for Attendance Table ─────────────────────────────
  const dateFilter    = document.getElementById('dateFilter');
  const attendanceBody = document.getElementById('attendanceTableBody');
  const filteredCount = document.getElementById('filteredCount');

  const applyDateFilter = () => {
    if (!attendanceBody) return;
    const filterVal = dateFilter ? dateFilter.value : '';
    const rows = attendanceBody.querySelectorAll('tr[data-date]');
    let visible = 0;
    rows.forEach(row => {
      const show = !filterVal || row.dataset.date === filterVal;
      row.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    if (filteredCount) {
      filteredCount.textContent = filterVal
        ? `Showing ${visible} record(s) for ${filterVal}`
        : `${rows.length} total record(s)`;
    }
  };

  if (dateFilter) {
    // Default to today
    dateFilter.value = new Date().toISOString().split('T')[0];
    dateFilter.addEventListener('change', applyDateFilter);
    applyDateFilter();  // apply on load
  }

  // ── Export CSV Button ─────────────────────────────────────────────
  const exportBtn = document.getElementById('exportBtn');
  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      const dateVal = dateFilter ? dateFilter.value : '';
      const url = '/api/admin/export_attendance' + (dateVal ? `?date=${dateVal}` : '');
      window.location.href = url;
    });
  }

  // ── Auto-sync marks ────────────────────────────────────────────────
  const autoSyncKey = 'marksAutoSynced';
  if (!sessionStorage.getItem(autoSyncKey)) {
    sessionStorage.setItem(autoSyncKey, '1');
    syncMarks(true);
  }
  setInterval(() => syncMarks(false), 60 * 1000);

  startAdminCamera();
});

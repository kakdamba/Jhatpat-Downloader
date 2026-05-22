document.addEventListener('DOMContentLoaded', async () => {
  const list = document.getElementById('list');
  const videoCountEl = document.getElementById('video-count');
  const scanActions = document.getElementById('scan-actions');
  const batchActions = document.getElementById('batch-actions');
  const selectAllCb = document.getElementById('select-all');
  const downloadSelectedBtn = document.getElementById('download-selected-btn');

  let currentTab = 'video';
  let mediaItems = { video: [], audio: [], image: [], subtitle: [] };
  let pageTitle = "Page";

  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const pageUrl = tab.url;

  const smartSites = ["youtube.com", "youtu.be", "instagram.com", "facebook.com", "pexels.com", "tiktok.com"];
  const isSmart = smartSites.some(s => pageUrl.includes(s));

  if (isSmart) {
    scanActions.style.display = 'flex';
    addFullWidthAction("Smart Download Link", pageUrl, true, "video");
  }

  // Request media items from content.js
  chrome.tabs.sendMessage(tab.id, { action: "getMedia" }, (items) => {
    if (!items || items.length === 0) {
      list.innerHTML = `<div class="empty-state"><p>No files found on this page.</p></div>`;
      if (!isSmart) {
        scanActions.style.display = 'flex';
        addFullWidthAction("Force Send Link", pageUrl, false, "video");
      }
      return;
    }

    // Group items
    items.forEach(item => {
      if (mediaItems[item.type]) mediaItems[item.type].push(item);
      pageTitle = item.title;
    });

    videoCountEl.innerText = `${items.length} Files Found`;

    // Update badges
    document.getElementById('badge-video').innerText = mediaItems.video.length;
    document.getElementById('badge-audio').innerText = mediaItems.audio.length;
    document.getElementById('badge-image').innerText = mediaItems.image.length;
    document.getElementById('badge-subtitle').innerText = mediaItems.subtitle.length;

    renderList();
  });

  // Tab logic
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTab = btn.dataset.tab;
      renderList();
    });
  });

  // Batch actions
  selectAllCb.addEventListener('change', (e) => {
    document.querySelectorAll('.item-checkbox').forEach(cb => {
      cb.checked = e.target.checked;
    });
  });

  downloadSelectedBtn.addEventListener('click', async () => {
    const checkboxes = document.querySelectorAll('.item-checkbox:checked');
    if (checkboxes.length === 0) return;
    
    let originalText = downloadSelectedBtn.innerText;
    downloadSelectedBtn.innerText = "Sending...";
    downloadSelectedBtn.disabled = true;

    for (let cb of checkboxes) {
      let index = parseInt(cb.dataset.index);
      let item = mediaItems[currentTab][index];
      // Simulate click on individual download btn to show spinning
      let itemBtn = document.getElementById(`dl-btn-${index}`);
      if (itemBtn) itemBtn.classList.add('sending');
      
      try {
        await fetch('http://127.0.0.1:5001/send_link', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ url: item.url, type: item.type, page_title: item.title })
        });
        if (itemBtn) {
          itemBtn.classList.remove('sending');
          itemBtn.classList.add('sent');
          itemBtn.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        }
      } catch(e) {}
      
      // small delay between requests
      await new Promise(r => setTimeout(r, 200));
    }

    downloadSelectedBtn.innerText = "Sent!";
    setTimeout(() => {
      downloadSelectedBtn.innerText = originalText;
      downloadSelectedBtn.disabled = false;
      selectAllCb.checked = false;
      document.querySelectorAll('.item-checkbox').forEach(c => c.checked = false);
    }, 2000);
  });

  function renderList() {
    list.innerHTML = "";
    selectAllCb.checked = false;
    let items = mediaItems[currentTab];
    
    if (items.length === 0) {
      batchActions.style.display = 'none';
      list.innerHTML = `<div class="empty-state"><p>No ${currentTab}s found.</p></div>`;
      return;
    }
    
    batchActions.style.display = 'flex';
    
    items.forEach((item, index) => {
      let ext = "LINK";
      if (item.url.includes('.')) ext = item.url.split('.').pop().split('?')[0].toUpperCase();
      if (ext.length > 4) ext = item.type.toUpperCase();

      let iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>`;
      if (item.type === 'audio') iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`;
      if (item.type === 'image') iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`;
      if (item.type === 'subtitle') iconSvg = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`;

      const div = document.createElement('div');
      div.className = 'video-item';
      div.innerHTML = `
        <input type="checkbox" class="item-checkbox" data-index="${index}">
        <div class="video-info" title="${item.url}" style="flex:1; overflow:hidden;">
          <div class="play-icon">${iconSvg}</div>
          <div class="video-details" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
            <div class="video-title" style="overflow: hidden; text-overflow: ellipsis;">${item.type.charAt(0).toUpperCase() + item.type.slice(1)} ${index+1}</div>
            <div class="video-meta">${item.res} • ${ext}</div>
          </div>
        </div>
        <button class="download-btn" id="dl-btn-${index}" aria-label="Download">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
        </button>
      `;

      const downloadBtn = div.querySelector('.download-btn');
      downloadBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        sendLink(item.url, downloadBtn, false, "", item.type, item.title);
      });

      list.appendChild(div);
    });
  }

  function addFullWidthAction(txt, url, isPrimary, type="video") {
    let b = document.createElement('button');
    b.className = "full-width-action";
    b.innerText = txt;
    if (isPrimary) {
      b.style.borderColor = "var(--accent-purple)";
      b.style.color = "var(--accent-purple)";
    }
    
    b.onclick = () => {
      let originalText = b.innerText;
      b.innerText = "SENDING...";
      sendLink(url, b, true, originalText, type, pageTitle);
    };
    scanActions.appendChild(b);
  }

  function sendLink(url, btnElement, isFullWidth = false, originalText = "", type="video", title="") {
    const originalContent = btnElement.innerHTML;
    if (!isFullWidth) btnElement.classList.add('sending');

    fetch('http://127.0.0.1:5001/send_link', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url, type: type, page_title: title})
    })
    .then(res => {
      if(res.ok) { 
        if (isFullWidth) {
          btnElement.innerText = "SENT!";
          btnElement.style.background = "var(--accent-green)";
          btnElement.style.color = "#000";
        } else {
          btnElement.classList.remove('sending');
          btnElement.classList.add('sent');
          btnElement.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        }
      } else { throw new Error(); }
    })
    .catch(() => { 
      if (isFullWidth) {
        btnElement.innerText = "OFFLINE";
        btnElement.style.borderColor = "#ef4444";
        btnElement.style.color = "#ef4444";
        setTimeout(() => { 
          btnElement.innerText = originalText; 
          btnElement.style.borderColor = "";
          btnElement.style.color = "";
        }, 2000);
      } else {
        btnElement.classList.remove('sending');
        btnElement.classList.add('error');
        btnElement.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>`;
        setTimeout(() => {
          btnElement.classList.remove('error');
          btnElement.innerHTML = originalContent;
        }, 2000);
      }
    });
  }
});

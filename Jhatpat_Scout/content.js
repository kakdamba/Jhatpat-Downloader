function getMediaItems() {
  let items = [];
  const pageTitle = document.title.replace(/[\\/:*?"<>|]/g, "_") || "Page"; // Safe folder name

  // 1. Videos & Audio
  document.querySelectorAll('video, audio, source, a[href*=".mp4"], a[href*=".mkv"], a[href*=".webm"], a[href*=".mp3"], a[href*=".wav"], a[href*=".ogg"]').forEach(el => {
    let src = el.src || el.href;
    if (!src || !src.startsWith('http')) return;
    
    let type = "video";
    if (el.tagName === 'AUDIO' || src.includes('.mp3') || src.includes('.wav') || src.includes('.ogg')) {
      type = "audio";
    }
    items.push({ type: type, url: src, res: type === "audio" ? "Audio" : "Auto", title: pageTitle });
  });

  // 2. Subtitles
  document.querySelectorAll('track[kind="subtitles"], track[kind="captions"], a[href*=".srt"], a[href*=".vtt"]').forEach(el => {
    let src = el.src || el.href;
    if (!src || !src.startsWith('http')) return;
    items.push({ type: "subtitle", url: src, res: "Sub", title: pageTitle });
  });

  // 3. High-Resolution Images
  document.querySelectorAll('img, a[href*=".jpg"], a[href*=".jpeg"], a[href*=".png"], a[href*=".webp"]').forEach(el => {
    let src = "";
    let width = 0;
    
    if (el.tagName === 'IMG') {
      // Check dimensions
      if (el.naturalWidth < 800 || el.naturalHeight < 600) return;
      
      src = el.src;
      width = el.naturalWidth;
      
      // Check srcset for highest res
      if (el.srcset) {
        let maxW = 0;
        let maxSrc = src;
        el.srcset.split(',').forEach(part => {
          let chunks = part.trim().split(' ');
          if (chunks.length === 2) {
            let w = parseInt(chunks[1]);
            if (w > maxW) {
              maxW = w;
              maxSrc = chunks[0];
            }
          }
        });
        if (maxW > width) {
          src = maxSrc;
          width = maxW;
        }
      }
      
      // Fix relative srcset URLs
      if (src && !src.startsWith('http')) {
        src = new URL(src, window.location.origin).href;
      }
      
    } else {
      src = el.href;
      width = 2000; // Assume linked images are high-res
    }
    
    if (!src || !src.startsWith('http')) return;
    
    let res = "HD";
    if (width >= 3840) res = "4K";
    else if (width >= 2560) res = "2K";
    
    items.push({ type: "image", url: src, res: res, title: pageTitle });
  });

  // Deduplicate by URL
  let uniqueItems = [];
  let seen = new Set();
  items.forEach(item => {
    if (!seen.has(item.url)) {
      seen.add(item.url);
      uniqueItems.push(item);
    }
  });

  return uniqueItems;
}

function countMedia() {
  let items = getMediaItems();
  try {
    chrome.runtime.sendMessage({
      action: "updateBadge",
      count: items.length
    });
  } catch (e) {
    // Context invalidated
  }
}

// Run on initial load
countMedia();
setInterval(countMedia, 3000);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getMedia") {
    sendResponse(getMediaItems());
  }
});

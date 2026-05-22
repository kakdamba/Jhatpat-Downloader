chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "updateBadge" && sender.tab && sender.tab.id) {
    if (request.count > 0) {
      chrome.action.setBadgeText({ text: request.count.toString(), tabId: sender.tab.id });
      chrome.action.setBadgeBackgroundColor({ color: "#8b5cf6", tabId: sender.tab.id }); // Jhatpat Purple
    } else {
      chrome.action.setBadgeText({ text: "", tabId: sender.tab.id });
    }
  }
});

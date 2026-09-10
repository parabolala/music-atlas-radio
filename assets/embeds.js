document.querySelectorAll(".soundcloud-embed").forEach((embed) => {
  const poster = embed.querySelector("img");
  const iframe = document.createElement("iframe");

  iframe.src = embed.dataset.soundcloudSrc;
  iframe.title = poster?.alt || "SoundCloud player";
  iframe.allow = "autoplay";
  iframe.loading = "lazy";
  iframe.referrerPolicy = "no-referrer";
  iframe.sandbox = "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox";

  embed.replaceChildren(iframe);
});

(function initRomanticAnimation() {
  // Wait until document.body is available (Next.js may run us too early).
  if (!document.body) {
    requestAnimationFrame(initRomanticAnimation);
    return;
  }

  // Flowers blooming on an ellipse around the title (transform/opacity only: cheap)
  const flowerChars = ["🌸", "🌷", "🌹", "🌸", "💮", "🌺"];
  const count = 12;
  const flowers = Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2 + 0.3;
    const x = Math.cos(angle) * 34; // vw
    const y = Math.sin(angle) * 22; // vh
    const size = 1.6 + (i % 3) * 0.5; // rem
    const delay = 0.24 + (i % 4) * 0.06;
    const spin = (i % 2 ? 1 : -1) * (40 + (i % 3) * 20);
    return `<span class="flower" style="--x:${x.toFixed(1)}vw;--y:${y.toFixed(1)}vh;--s:${size}rem;--d:${delay}s;--r:${spin}deg">${flowerChars[i % flowerChars.length]}</span>`;
  }).join("");

  const introDiv = document.createElement("div");
  introDiv.id = "romantic-intro";
  introDiv.innerHTML = `
    ${flowers}
    <div class="romantic-text">
      <span class="heart">❤️</span>
      <span class="word">FormiCloud</span>
    </div>
  `;
  document.body.prepend(introDiv);

  // 1s total: animation ends at ~0.76s, then a 0.24s fade-out and cleanup.
  setTimeout(() => {
    introDiv.classList.add("fade-out");
    setTimeout(() => introDiv.remove(), 240);
  }, 760);
})();

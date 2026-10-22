(function initRomanticAnimation() {
  // In Next.js, DOMContentLoaded might have already fired, or we might be too early.
  // We wait until document.body is available.
  if (!document.body) {
    requestAnimationFrame(initRomanticAnimation);
    return;
  }
  
  // Create the overlay container
  const introDiv = document.createElement("div");
  introDiv.id = "romantic-intro";
  
  const text = "FormiCloud";
  
  // Create spans for each letter with a staggered --i variable for CSS
  const lettersHtml = text.split('').map((char, index) => {
    return `<span style="--i: ${index}">${char}</span>`;
  }).join('');
  
  // Add the heart at the end
  const heartHtml = `<span class="heart" style="--i: ${text.length}">❤️</span>`;
  
  introDiv.innerHTML = `
    <div class="romantic-text">
      ${lettersHtml}
      ${heartHtml}
    </div>
  `;
  
  // Prepend to body so it sits on top immediately
  document.body.prepend(introDiv);
  
  // Let the animation play (letters take ~2 seconds total to finish appearing)
  // Then we wait a tiny bit to admire it, and fade out.
  setTimeout(() => {
    introDiv.classList.add("fade-out");
    
    // Completely remove it from the DOM after the fade out transition (0.8s)
    setTimeout(() => {
      introDiv.remove();
    }, 1000);
    
  }, 2500); // 2.5 seconds total screen time
})();

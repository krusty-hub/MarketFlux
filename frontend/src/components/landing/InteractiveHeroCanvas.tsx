import React, { useEffect, useRef } from 'react';

export const InteractiveHeroCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };

    window.addEventListener('resize', handleResize);

    // Candle and path points simulation
    const pointsCount = 36;
    let offset = 0;

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      const isDark = document.documentElement.classList.contains('dark');

      // 1. Subtle Grid Lines
      ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.03)';
      ctx.lineWidth = 1;
      const stepX = width / 12;
      const stepY = height / 6;

      for (let x = 0; x < width; x += stepX) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += stepY) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // 2. Liquidity Zones (Soft translucent horizontal bands)
      ctx.fillStyle = isDark ? 'rgba(16, 185, 129, 0.03)' : 'rgba(16, 185, 129, 0.02)';
      ctx.fillRect(0, height * 0.28, width, height * 0.12);
      ctx.fillStyle = isDark ? 'rgba(239, 68, 68, 0.02)' : 'rgba(239, 68, 68, 0.015)';
      ctx.fillRect(0, height * 0.65, width, height * 0.1);

      // 3. Flowing Price Wave
      ctx.beginPath();
      const points: { x: number; y: number }[] = [];
      const baseY = height * 0.5;

      for (let i = 0; i <= pointsCount; i++) {
        const x = (i / pointsCount) * width;
        const wave1 = Math.sin((i * 0.3) + offset) * 35;
        const wave2 = Math.cos((i * 0.15) - offset * 0.5) * 20;
        const y = baseY + wave1 + wave2 - (i * 1.8);
        points.push({ x, y });

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          const prev = points[i - 1];
          const cx = (prev.x + x) / 2;
          const cy = (prev.y + y) / 2;
          ctx.quadraticCurveTo(prev.x, prev.y, cx, cy);
        }
      }

      // Stroke refined emerald green path
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.shadowColor = '#10b981';
      ctx.shadowBlur = isDark ? 8 : 4;
      ctx.stroke();
      ctx.shadowBlur = 0; // reset shadow

      // Gradient Fill Under Wave
      ctx.lineTo(width, height);
      ctx.lineTo(0, height);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, baseY - 50, 0, height);
      grad.addColorStop(0, isDark ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.04)');
      grad.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
      ctx.fillStyle = grad;
      ctx.fill();

      // 4. Candlestick Bars Overlay
      const candleWidth = 5;
      for (let i = 2; i < pointsCount; i += 3) {
        const p = points[i];
        const isUp = i % 2 === 0;
        const candleHeight = 22 + Math.sin(i + offset) * 12;
        const wickHeight = candleHeight + 14;

        ctx.strokeStyle = isUp ? '#10b981' : 'rgba(239, 68, 68, 0.6)';
        ctx.lineWidth = 1;

        // Wick
        ctx.beginPath();
        ctx.moveTo(p.x, p.y - wickHeight / 2);
        ctx.lineTo(p.x, p.y + wickHeight / 2);
        ctx.stroke();

        // Body
        ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.4)';
        ctx.fillRect(p.x - candleWidth / 2, p.y - candleHeight / 2, candleWidth, candleHeight);
      }

      // 5. Probability Forecast Cone (Right Side)
      const lastPoint = points[points.length - 1];
      ctx.beginPath();
      ctx.moveTo(lastPoint.x, lastPoint.y);
      ctx.lineTo(width, lastPoint.y - 45);
      ctx.lineTo(width, lastPoint.y + 25);
      ctx.closePath();
      const coneGrad = ctx.createLinearGradient(lastPoint.x, 0, width, 0);
      coneGrad.addColorStop(0, 'rgba(53, 168, 120, 0.25)');
      coneGrad.addColorStop(1, 'rgba(53, 168, 120, 0.02)');
      ctx.fillStyle = coneGrad;
      ctx.fill();

      // Glowing head pulse
      ctx.beginPath();
      ctx.arc(lastPoint.x, lastPoint.y, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = '#35A878';
      ctx.fill();

      offset += 0.015;
      animationFrameId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full pointer-events-none opacity-80"
    />
  );
};

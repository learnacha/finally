import React, { useRef, useEffect } from "react";

interface SparklineProps {
  data: { time: number; price: number }[];
  width?: number;
  height?: number;
  positive?: boolean;
}

export function Sparkline({ data, width = 80, height = 28, positive }: SparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || data.length < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const prices = data.map((d) => d.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;

    const color =
      positive === true
        ? "#3fb950"
        : positive === false
        ? "#f85149"
        : prices[prices.length - 1] >= prices[0]
        ? "#3fb950"
        : "#f85149";

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";

    for (let i = 0; i < prices.length; i++) {
      const x = (i / (prices.length - 1)) * width;
      const y = height - ((prices[i] - min) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Fill area under the line
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = color.replace(")", ", 0.15)").replace("rgb", "rgba").replace("#", "");
    // Use a simpler fill approach
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + "30");
    gradient.addColorStop(1, color + "05");
    ctx.fillStyle = gradient;
    ctx.fill();
  }, [data, width, height, positive]);

  return (
    <canvas
      ref={canvasRef}
      style={{ display: "block" }}
    />
  );
}

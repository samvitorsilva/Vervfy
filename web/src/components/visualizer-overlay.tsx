"use client";

import { useEffect, useRef } from "react";
import { usePlayerStore } from "@/store/player-store";

interface AudioGraph {
  context: AudioContext;
  analyser: AnalyserNode;
}

const audioGraphs = new WeakMap<HTMLAudioElement, AudioGraph>();

export default function VisualizerOverlay({ onClose }: { onClose: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number | null>(null);
  const frequenciesRef = useRef<Uint8Array<ArrayBuffer> | null>(null);
  const phasesRef = useRef<number[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const audio = usePlayerStore.getState().audioElement;
    if (!canvas || !audio) return;

    let graph = audioGraphs.get(audio);
    if (!graph) {
      const AudioContextConstructor =
        window.AudioContext ??
        (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextConstructor) return;
      try {
        const context = new AudioContextConstructor();
        const analyser = context.createAnalyser();
        analyser.fftSize = 256;
        const source = context.createMediaElementSource(audio);
        source.connect(analyser);
        analyser.connect(context.destination);
        graph = { context, analyser };
        audioGraphs.set(audio, graph);
      } catch (error) {
        console.warn("Visualizer audio analysis unavailable", error);
        return;
      }
    }
    frequenciesRef.current = new Uint8Array(graph.analyser.frequencyBinCount);
    phasesRef.current = new Array(graph.analyser.frequencyBinCount).fill(0);

    if (graph.context.state === "suspended") void graph.context.resume();
    const draw = () => {
      const ctx = canvas.getContext("2d");
      const data = frequenciesRef.current;
      if (!ctx || !data) return;
      const rect = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.round(rect.width * ratio));
      const height = Math.max(1, Math.round(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      ctx.clearRect(0, 0, width, height);
      graph.analyser.getByteFrequencyData(data);

      const centerX = width / 2;
      const centerY = height / 2;
      const baseRadius = Math.min(width, height) * 0.2;
      ctx.save();
      ctx.translate(centerX, centerY);
      const glow = ctx.createRadialGradient(0, 0, baseRadius * 0.3, 0, 0, baseRadius * 2.2);
      glow.addColorStop(0, "rgba(139,127,255,.18)");
      glow.addColorStop(0.6, "rgba(84,232,212,.06)");
      glow.addColorStop(1, "rgba(8,10,16,0)");
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, baseRadius * 2.2, 0, Math.PI * 2);
      ctx.fill();

      const bars = 64;
      const phases = phasesRef.current;
      for (let index = 0; index < bars; index += 1) {
        const value = data[index] / 255;
        phases[index] += (value - phases[index]) * 0.16;
        const angle = (index / bars) * Math.PI * 2 - Math.PI / 2;
        const startRadius = baseRadius + 10;
        const endRadius = startRadius + phases[index] * baseRadius * 0.95;
        const x1 = Math.cos(angle) * startRadius;
        const y1 = Math.sin(angle) * startRadius;
        const x2 = Math.cos(angle) * endRadius;
        const y2 = Math.sin(angle) * endRadius;
        const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
        gradient.addColorStop(0, "rgba(84,232,212,.9)");
        gradient.addColorStop(1, "rgba(139,127,255,.75)");
        ctx.strokeStyle = gradient;
        ctx.lineWidth = Math.max(2, width * 0.004);
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      ctx.beginPath();
      ctx.arc(0, 0, baseRadius, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(242,243,247,.06)";
      ctx.fill();
      ctx.strokeStyle = "rgba(212,208,255,.36)";
      ctx.lineWidth = Math.max(1, width * 0.002);
      ctx.stroke();
      ctx.restore();
      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    };
  }, []);

  return (
    <div className="viz-overlay open" role="dialog" aria-modal="true" aria-label="Audio visualizer">
      <div className="viz-layout">
        <div className="viz-stage"><canvas ref={canvasRef} aria-label="Audio frequency visualizer" /></div>
      </div>
      <button className="viz-close" type="button" aria-label="Close visualizer" onClick={onClose}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m7 7 10 10M17 7 7 17" /></svg>
      </button>
    </div>
  );
}

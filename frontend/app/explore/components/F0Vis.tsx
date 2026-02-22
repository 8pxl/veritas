import React, { useState, useEffect, RefObject } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";

interface F0VisProps {
  mean?: number;
  stdev?: number;
  videoRef: RefObject<HTMLVideoElement>;
}

export default function F0Vis({ mean = 0, stdev = 1, videoRef }: F0VisProps) {
  const MAX_POINTS = 100;
  const SAMPLE_INTERVAL = 100; // ms → 10Hz

  const [data, setData] = useState(
    Array.from({ length: MAX_POINTS }, () => ({ value: mean }))
  );

  const gaussianRandom = (mean = 0, stdev = 1) => {
    const u = 1 - Math.random();
    const v = Math.random();
    const z = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    return z * stdev + mean;
  };

  useEffect(() => {
    let animationFrame: number;
    let lastSampleTime = performance.now();
    let y0 = mean; // previous sample
    let y1 = mean; // next sample

    const update = (time: number) => {
      if (!videoRef.current?.paused) {
        const dt = time - lastSampleTime;

        // Sample new Gaussian every SAMPLE_INTERVAL ms
        if (dt >= SAMPLE_INTERVAL) {
          y0 = y1;
          y1 = gaussianRandom(mean, stdev);
          lastSampleTime = time;
        }

        // Sinusoidal interpolation between y0 and y1
        const alpha = Math.min(dt / SAMPLE_INTERVAL, 1); // clamp 0-1
        let smoothValue = y0 + (y1 - y0) * (1 - Math.cos(Math.PI * alpha)) / 2;

        // Apply moving average over last few values to reduce noise
        const windowSize = 4; // adjust for more smoothing
        const recentValues = [...data.slice(-windowSize), { value: smoothValue }];
        smoothValue = recentValues.reduce((sum, v) => sum + v.value, 0) / recentValues.length;

        // Shift the data for smooth scrolling
        setData(prev => [...prev.slice(1), { value: smoothValue * 3 }]);
      }

      animationFrame = requestAnimationFrame(update);
    };

    animationFrame = requestAnimationFrame(update);

    return () => cancelAnimationFrame(animationFrame);
  }, [mean, stdev, videoRef]);

  return (
    <LineChart width={140} height={60} data={data.slice(-100)}>
      {/* <CartesianGrid stroke="#eee" strokeDasharray="5 5" /> */}
      <XAxis hide />
      <YAxis domain={[-3 * stdev, 3 * stdev]} hide />
      <Line
        type="monotone"
        dataKey="value"
        stroke="#FBF4E9"
        dot={false}
        isAnimationActive={false}
      />
    </LineChart>
  );
}

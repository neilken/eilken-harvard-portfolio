"use client";
import AboutSection from "@/components/about/AboutSection";


export default function Page() {
  return (
    <div className="min-h-screen w-full bg-gray-50 p-8 flex flex-col items-center">
      <h1 className="text-4xl font-extrabold mb-12 text-center">About Stock Busters</h1>

      <AboutSection title="Our Mission">
        Stock Busters exists to empower retail investors by cutting through market noise
        and delivering clean, actionable insights.
      </AboutSection>

      <AboutSection title="The Problem We Solve">
        Most retail investors face information overload and analysis paralysis.
      </AboutSection>

      <AboutSection title="Our Solution">
        Stock Busters uses AI to simplify market research and generate actionable insights.
      </AboutSection>

      <AboutSection title="Why We Built Stock Busters">
        Retail investors deserve institutional-grade clarity and strategy.
      </AboutSection>
    </div>
  );
}
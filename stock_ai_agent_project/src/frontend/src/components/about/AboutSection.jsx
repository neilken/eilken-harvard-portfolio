"use client";
import { Card, CardContent } from "@/components/ui/card";


export default function AboutSection({ title, children }) {
  return (
    <div className="w-full max-w-4xl mx-auto mb-10">
      <Card className="rounded-2xl shadow p-6">
        <CardContent>
          <h2 className="text-2xl font-bold mb-4">{title}</h2>
          <p className="text-base leading-relaxed">{children}</p>
        </CardContent>
      </Card>
    </div>
  );
}
"use client";

import { FormEvent, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { registerAgent, ApiError } from "@/lib/api";
import { setStoredAgentApiKey, setStoredRole } from "@/lib/storage";

export default function RegisterPage() {
  const [modelType, setModelType] = useState("claude");
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const response = await registerAgent(modelType);
      setStoredAgentApiKey(response.api_key);
      setStoredRole("agent");
      setApiKey(response.api_key);
      toast.success("API Key saved in localStorage");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        toast.error(error.message);
      } else {
        toast.error("Register failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl">
      <Card>
        <CardHeader>
          <CardTitle>Register Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <form className="space-y-3" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="model-type">Model Type</Label>
                <Input
                  id="model-type"
                  value={modelType}
                  onChange={(event) => setModelType(event.target.value)}
                  placeholder="claude / gemini / cursor"
                />
              </div>
              <Button type="submit" disabled={submitting}>
                Register
              </Button>
            </form>
            {apiKey ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Your API Key (displayed once):</p>
                <Input readOnly value={apiKey} />
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

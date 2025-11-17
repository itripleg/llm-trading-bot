"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Play, Square, AlertOctagon } from "lucide-react";
import { useBotControls } from "../hooks/useBotStatus";
import { useToast } from "@/hooks/use-toast";

export function BotControls() {
  const { startBot, stopBot, emergencyStop, controlling } = useBotControls();
  const { toast } = useToast();
  const [lastAction, setLastAction] = useState<string | null>(null);

  const handleStart = async () => {
    const result = await startBot();
    setLastAction("start");
    toast({
      title: result.success ? "Bot Started" : "Failed to Start",
      description: result.message,
      variant: result.success ? "default" : "destructive",
    });
  };

  const handleStop = async () => {
    const result = await stopBot();
    setLastAction("stop");
    toast({
      title: result.success ? "Bot Stopped" : "Failed to Stop",
      description: result.message,
      variant: result.success ? "default" : "destructive",
    });
  };

  const handleEmergencyStop = async () => {
    const result = await emergencyStop();
    setLastAction("emergency");
    toast({
      title: result.success ? "Emergency Stop Activated" : "Emergency Stop Failed",
      description: result.message,
      variant: result.success ? "default" : "destructive",
    });
  };

  return (
    <Card className="unified-card">
      <CardHeader>
        <CardTitle>Bot Controls</CardTitle>
        <CardDescription>
          Start, stop, or emergency halt the trading bot
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {/* Start Button */}
          <Button
            onClick={handleStart}
            disabled={controlling}
            variant="default"
            className="bg-green-600 hover:bg-green-700"
          >
            <Play className="w-4 h-4 mr-2" />
            Start Bot
          </Button>

          {/* Stop Button */}
          <Button
            onClick={handleStop}
            disabled={controlling}
            variant="secondary"
          >
            <Square className="w-4 h-4 mr-2" />
            Stop Bot
          </Button>

          {/* Emergency Stop Button with Confirmation */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                disabled={controlling}
                variant="destructive"
              >
                <AlertOctagon className="w-4 h-4 mr-2" />
                Emergency Stop
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Emergency Stop Bot?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will immediately halt the bot and close all open positions.
                  This action should only be used in emergency situations.
                  Are you absolutely sure?
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleEmergencyStop}
                  className="bg-destructive hover:bg-destructive/90"
                >
                  Emergency Stop
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        {lastAction && (
          <p className="text-xs text-muted-foreground mt-4">
            Last action: {lastAction} • {new Date().toLocaleTimeString()}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

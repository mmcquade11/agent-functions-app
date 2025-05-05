// src/components/AgentEditModal.tsx

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

type Agent = {
  id: string;
  name: string;
  description: string;
  agent_code: string;
  status: string;
};

interface Props {
  agent: Agent | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (updated: Agent) => void;
}

export default function AgentEditModal({
  agent,
  isOpen,
  onClose,
  onSave,
}: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [code, setCode] = useState("");

  useEffect(() => {
    if (agent) {
      setName(agent.name);
      setDescription(agent.description);
      setCode(agent.agent_code);
    }
  }, [agent]);

  const handleSave = () => {
    if (!agent) return;
    onSave({
      ...agent,
      name,
      description,
      agent_code: code,
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Edit Agent</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Agent Name"
          />
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Agent Description"
            rows={3}
          />
          <Textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Agent Code"
            rows={10}
          />
        </div>

        <DialogFooter className="pt-4">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
"use client";

import React, { useState, useEffect } from "react";
import {
  Network,
  X,
  Loader2,
  AlertCircle,
  Layers,
  ArrowRight,
  MessageSquare,
  FileCode,
  Shield,
  Database,
  Server,
  Sliders,
  Box,
} from "lucide-react";
import { ArchitectureMapResponse, ArchitectureMapNode, ArchitectureMapEdge } from "@/lib/types";
import { getArchitectureMap } from "@/lib/api";

interface ArchitectureMapModalProps {
  repoId: string;
  repoName: string;
  isOpen: boolean;
  onClose: () => void;
  onSelectQuestion?: (q: string) => void;
}

export const ArchitectureMapModal: React.FC<ArchitectureMapModalProps> = ({
  repoId,
  repoName,
  isOpen,
  onClose,
  onSelectQuestion,
}) => {
  const [mapData, setMapData] = useState<ArchitectureMapResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<ArchitectureMapNode | null>(null);

  useEffect(() => {
    if (isOpen && !mapData) {
      setLoading(true);
      setError(null);
      getArchitectureMap(repoId)
        .then((res) => {
          setMapData(res);
          if (res.nodes.length > 0) setSelectedNode(res.nodes[0]);
        })
        .catch((err) => setError(err?.message || "Failed to load architecture map."))
        .finally(() => setLoading(false));
    }
  }, [isOpen, repoId, mapData]);

  if (!isOpen) return null;

  const getLayerColor = (type: string) => {
    switch (type.toLowerCase()) {
      case "api":
        return { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", icon: Server };
      case "services":
        return { bg: "bg-teal-50", text: "text-[#0B6E5F]", border: "border-teal-200", icon: Layers };
      case "models":
        return { bg: "bg-indigo-50", text: "text-indigo-700", border: "border-indigo-200", icon: Box };
      case "db":
        return { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-200", icon: Database };
      case "core":
      case "config":
        return { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200", icon: Sliders };
      default:
        return { bg: "bg-gray-50", text: "text-gray-700", border: "border-gray-200", icon: FileCode };
    }
  };

  const handleAskAboutModule = (node: ArchitectureMapNode) => {
    if (onSelectQuestion) {
      onSelectQuestion(`Explain the architecture and responsibilities of the ${node.label} module.`);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-5xl w-full max-h-[90vh] shadow-2xl border border-[#E5E2DB] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#EAE8E2] bg-[#FAF9F6] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[#E6F4F1] text-[#0B6E5F] flex items-center justify-center shadow-xs">
              <Network className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-[#1C2024] leading-tight">
                Architecture & Dependency Map
              </h2>
              <p className="text-xs text-[#636A74]">
                Interactive module layers, dependencies, and component relationships for {repoName}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-black/5 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-[#0B6E5F]">
              <Loader2 className="w-8 h-8 animate-spin" />
              <p className="text-sm font-semibold text-[#1C2024]">Extracting architectural module graph...</p>
              <p className="text-xs text-[#636A74]">Parsing cross-module imports and dependency topology</p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {mapData && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Cols: Module Nodes & Relationship List */}
              <div className="lg:col-span-2 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-[#636A74]">
                    Identified Modules ({mapData.nodes.length})
                  </span>
                  <span className="text-[11px] text-[#A09D96]">
                    Click any module to inspect or ask questions
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {mapData.nodes.map((node) => {
                    const style = getLayerColor(node.module_type);
                    const isSelected = selectedNode?.id === node.id;
                    const IconComp = style.icon;

                    return (
                      <div
                        key={node.id}
                        onClick={() => setSelectedNode(node)}
                        className={`p-4 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? "bg-white border-[#0B6E5F] ring-2 ring-[#0B6E5F]/20 shadow-md"
                            : "bg-[#FAF9F6] border-[#EAE8E2] hover:bg-white hover:border-[#BDE3DC] shadow-xs"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <div className={`w-7 h-7 rounded-lg ${style.bg} ${style.text} flex items-center justify-center`}>
                              <IconComp className="w-3.5 h-3.5" />
                            </div>
                            <div>
                              <h4 className="text-xs font-bold text-[#1C2024]">
                                {node.label}
                              </h4>
                              <span className="text-[10px] uppercase font-semibold text-[#636A74]">
                                {node.module_type}
                              </span>
                            </div>
                          </div>

                          <span className="text-[11px] font-mono text-[#A09D96]">
                            {node.file_count} files
                          </span>
                        </div>

                        {node.description && (
                          <p className="text-[11px] text-[#636A74] mt-2 line-clamp-2 leading-relaxed">
                            {node.description}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Inter-Module Dependency Edges */}
                {mapData.edges.length > 0 && (
                  <div className="pt-2 space-y-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-[#636A74]">
                      Detected Module Dependencies ({mapData.edges.length})
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {mapData.edges.map((edge, idx) => (
                        <div
                          key={idx}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-[#E5E2DB] text-[11px] text-[#1C2024] shadow-xs"
                        >
                          <span className="font-semibold">{edge.source}</span>
                          <ArrowRight className="w-3 h-3 text-[#0B6E5F]" />
                          <span className="font-semibold">{edge.target}</span>
                          <span className="text-[10px] text-[#A09D96]">({edge.import_count} imports)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Col: Selected Module Deep Dive */}
              {selectedNode && (
                <div className="bg-[#FAF9F6] border border-[#E5E2DB] rounded-2xl p-5 space-y-4 flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-[#0B6E5F]">
                        {selectedNode.module_type} Layer
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-[#1C2024]">
                      {selectedNode.label} Module
                    </h3>

                    <div className="space-y-2 text-xs text-[#636A74]">
                      <div className="flex justify-between py-1 border-b border-[#EAE8E2]">
                        <span>File Count:</span>
                        <span className="font-semibold text-[#1C2024]">{selectedNode.file_count}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-[#EAE8E2]">
                        <span>Total Lines:</span>
                        <span className="font-semibold text-[#1C2024]">{selectedNode.line_count} LOC</span>
                      </div>
                      <div className="py-1">
                        <span className="block text-[11px] font-semibold text-[#1C2024] mb-1">Module Purpose:</span>
                        <p className="leading-relaxed text-[11px]">
                          {selectedNode.description || "Core repository component handling internal routines."}
                        </p>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleAskAboutModule(selectedNode)}
                    className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#1C2024] hover:bg-black transition-colors cursor-pointer shadow-xs"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Ask Question About This Module</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

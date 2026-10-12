"use client";

import React, { useState } from "react";
import { Check, Copy, Terminal, FileCode } from "lucide-react";
import { Citation } from "@/lib/types";

interface SafeMarkdownProps {
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

export const SafeMarkdown: React.FC<SafeMarkdownProps> = ({
  content,
  citations = [],
  onCitationClick,
}) => {
  // Split by code block fences (```)
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-[#1C2024]">
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          // Code block parsing
          const lines = part.slice(3, -3).trim().split("\n");
          let language = "";
          let code = part.slice(3, -3);

          if (lines.length > 0 && lines[0].trim().length > 0 && !lines[0].includes(" ")) {
            language = lines[0].trim();
            code = lines.slice(1).join("\n");
          }

          return <CodeBlock key={index} code={code.trim()} language={language} />;
        }

        // Markdown blocks (paragraphs, lists, headings)
        return (
          <FormattedBlocks
            key={index}
            text={part}
            citations={citations}
            onCitationClick={onCitationClick}
          />
        );
      })}
    </div>
  );
};

interface CodeBlockProps {
  code: string;
  language?: string;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ code, language }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = code.split("\n");
  const displayLang = language?.toLowerCase() || "code";

  return (
    <div className="my-2.5 rounded-xl overflow-hidden border border-[#2D333B] bg-[#16191E] text-[#E6E8EB] shadow-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#1F242C] border-b border-[#2D333B] text-[11px] text-[#8B93A0]">
        <div className="flex items-center gap-1.5 font-mono">
          <Terminal className="w-3.5 h-3.5 text-[#0B6E5F]" />
          <span className="font-semibold text-white/90">{displayLang}</span>
          <span className="text-white/40">·</span>
          <span className="text-[10px] text-white/60">{lines.length} {lines.length === 1 ? "line" : "lines"}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-white/10 text-white/90 hover:text-white transition-colors cursor-pointer"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-emerald-400 font-medium">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>

      <div className="p-3 overflow-x-auto max-h-80 overflow-y-auto text-xs font-mono leading-relaxed">
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr key={idx} className="hover:bg-white/[0.04] transition-colors">
                <td className="pr-3 select-none text-right text-[#57606A] w-6 align-top font-mono text-[11px]">
                  {idx + 1}
                </td>
                <td className="whitespace-pre font-mono text-[#E6E8EB] pl-1">
                  {line || " "}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

interface FormattedBlocksProps {
  text: string;
  citations: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

const FormattedBlocks: React.FC<FormattedBlocksProps> = ({
  text,
  citations,
  onCitationClick,
}) => {
  if (!text.trim()) return null;

  // Split into paragraphs / blocks by double newlines
  const blocks = text.split(/\n\n+/);

  return (
    <>
      {blocks.map((block, bIdx) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        const lines = trimmed.split("\n");

        // Check for Headings (#, ##, ###)
        if (lines.length === 1 && /^#{1,4}\s/.test(lines[0])) {
          const match = lines[0].match(/^(#{1,4})\s+(.*)$/);
          if (match) {
            const level = match[1].length;
            const headingText = match[2];

            if (level === 1 || level === 2) {
              return (
                <h3
                  key={bIdx}
                  className="text-sm font-bold text-[#1C2024] pt-2 pb-1 border-b border-[#EAE8E2] flex items-center gap-2"
                >
                  <InlineFormatter
                    text={headingText}
                    citations={citations}
                    onCitationClick={onCitationClick}
                  />
                </h3>
              );
            }

            return (
              <h4
                key={bIdx}
                className="text-xs font-bold uppercase tracking-wider text-[#0B6E5F] pt-2 pb-0.5 flex items-center gap-1.5"
              >
                <span className="w-1.5 h-3 bg-[#0B6E5F] rounded-full inline-block" />
                <InlineFormatter
                  text={headingText}
                  citations={citations}
                  onCitationClick={onCitationClick}
                />
              </h4>
            );
          }
        }

        // Check if all or most lines are bullet points (- , * , • )
        const isBulletList = lines.every((l) =>
          /^[-*•]\s+/.test(l.trim())
        );

        if (isBulletList) {
          return (
            <ul key={bIdx} className="space-y-2 my-2 pl-1">
              {lines.map((l, lIdx) => (
                <li key={lIdx} className="flex items-start gap-2.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#0B6E5F] mt-2 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <InlineFormatter
                      text={l.trim().replace(/^[-*•]\s+/, "")}
                      citations={citations}
                      onCitationClick={onCitationClick}
                    />
                  </div>
                </li>
              ))}
            </ul>
          );
        }

        // Check if all lines are numbered points (1. , 2. )
        const isNumberedList = lines.every((l) => /^\d+\.\s+/.test(l.trim()));

        if (isNumberedList) {
          return (
            <div key={bIdx} className="space-y-2 my-2.5 pl-1">
              {lines.map((l, lIdx) => {
                const match = l.trim().match(/^(\d+)\.\s+(.*)$/);
                const num = match ? match[1] : `${lIdx + 1}`;
                const rest = match ? match[2] : l.trim();

                return (
                  <div key={lIdx} className="flex items-start gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-[#E6F4F1] text-[#0B6E5F] font-bold text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                      {num}
                    </span>
                    <div className="flex-1 min-w-0">
                      <InlineFormatter
                        text={rest}
                        citations={citations}
                        onCitationClick={onCitationClick}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          );
        }

        // Mixed block: check line by line
        return (
          <div key={bIdx} className="space-y-1.5">
            {lines.map((l, lIdx) => {
              const lTrim = l.trim();
              if (!lTrim) return null;

              // Headings inside mixed block (#, ##, ###, ####)
              if (/^#{1,4}\s/.test(lTrim)) {
                const match = lTrim.match(/^(#{1,4})\s+(.*)$/);
                if (match) {
                  const level = match[1].length;
                  const headingText = match[2];

                  if (level === 1 || level === 2) {
                    return (
                      <h3
                        key={lIdx}
                        className="text-sm font-bold text-[#1C2024] pt-2.5 pb-1 border-b border-[#EAE8E2] flex items-center gap-2"
                      >
                        <InlineFormatter
                          text={headingText}
                          citations={citations}
                          onCitationClick={onCitationClick}
                        />
                      </h3>
                    );
                  }

                  return (
                    <h4
                      key={lIdx}
                      className="text-xs font-bold uppercase tracking-wider text-[#0B6E5F] pt-2 pb-0.5 flex items-center gap-1.5"
                    >
                      <span className="w-1.5 h-3 bg-[#0B6E5F] rounded-full inline-block" />
                      <InlineFormatter
                        text={headingText}
                        citations={citations}
                        onCitationClick={onCitationClick}
                      />
                    </h4>
                  );
                }
              }

              if (/^[-*•]\s+/.test(lTrim)) {
                return (
                  <div key={lIdx} className="flex items-start gap-2.5 pl-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#0B6E5F] mt-2 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <InlineFormatter
                        text={lTrim.replace(/^[-*•]\s+/, "")}
                        citations={citations}
                        onCitationClick={onCitationClick}
                      />
                    </div>
                  </div>
                );
              }

              if (/^\d+\.\s+/.test(lTrim)) {
                const match = lTrim.match(/^(\d+)\.\s+(.*)$/);
                const num = match ? match[1] : `${lIdx + 1}`;
                const rest = match ? match[2] : lTrim;

                return (
                  <div key={lIdx} className="flex items-start gap-2.5 pl-1 my-1">
                    <span className="w-5 h-5 rounded-full bg-[#E6F4F1] text-[#0B6E5F] font-bold text-xs flex items-center justify-center flex-shrink-0 mt-0.5">
                      {num}
                    </span>
                    <div className="flex-1 min-w-0">
                      <InlineFormatter
                        text={rest}
                        citations={citations}
                        onCitationClick={onCitationClick}
                      />
                    </div>
                  </div>
                );
              }

              return (
                <p key={lIdx} className="leading-relaxed">
                  <InlineFormatter
                    text={lTrim}
                    citations={citations}
                    onCitationClick={onCitationClick}
                  />
                </p>
              );
            })}
          </div>
        );
      })}
    </>
  );
};

interface InlineFormatterProps {
  text: string;
  citations: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

const InlineFormatter: React.FC<InlineFormatterProps> = ({
  text,
  citations,
  onCitationClick,
}) => {
  // Regex to split on:
  // 1. Inline code: `...`
  // 2. Bold text: **...**
  // 3. Citations: [File: ... Lines: ...] or [File: ... Line: ...]
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[File:[^\]]+\])/g);

  return (
    <>
      {tokens.map((token, idx) => {
        // Inline code
        if (token.startsWith("`") && token.endsWith("`")) {
          return (
            <code
              key={idx}
              className="px-1.5 py-0.5 rounded-md bg-[#F4F2EE] text-[#1C2024] font-mono text-[12px] font-semibold border border-[#E2DFD7] shadow-2xs"
            >
              {token.slice(1, -1)}
            </code>
          );
        }

        // Bold
        if (token.startsWith("**") && token.endsWith("**")) {
          return (
            <strong key={idx} className="font-semibold text-[#1C2024]">
              {token.slice(2, -2)}
            </strong>
          );
        }

        // Citation token: [File: path, Lines: 1-10]
        if (token.startsWith("[File:") && token.endsWith("]")) {
          // Parse file and line
          const match = token.match(/\[File:\s*([^,]+),\s*Lines?:?\s*(\d+)(?:-(\d+))?.*?\]/i);
          const rawFilePath = match ? match[1].trim() : "";
          const startLine = match ? parseInt(match[2], 10) : 1;
          const endLine = match && match[3] ? parseInt(match[3], 10) : startLine;

          const fileName = rawFilePath.split("/").pop() || rawFilePath;
          const lineStr = startLine === endLine ? `L${startLine}` : `L${startLine}-${endLine}`;

          // Find matching citation object if available
          const matchedCit = citations.find(
            (c) =>
              c.file_path === rawFilePath ||
              c.file_path.endsWith(rawFilePath) ||
              rawFilePath.endsWith(c.file_path)
          ) || {
            file_path: rawFilePath,
            start_line: startLine,
            end_line: endLine,
          };

          return (
            <button
              key={idx}
              type="button"
              onClick={() => onCitationClick?.(matchedCit)}
              title={`View source: ${rawFilePath} (Lines ${startLine}-${endLine})`}
              className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md bg-[#E6F4F1] hover:bg-[#D3EFE9] text-[#0B6E5F] font-mono text-[11px] font-semibold border border-[#BDE3DC] transition-all cursor-pointer shadow-2xs group"
            >
              <FileCode className="w-3 h-3 text-[#0B6E5F] group-hover:scale-110 transition-transform" />
              <span>{fileName}:{lineStr}</span>
            </button>
          );
        }

        return <span key={idx}>{token}</span>;
      })}
    </>
  );
};

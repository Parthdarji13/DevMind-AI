"use client";

import React, { useState } from "react";
import { Check, Copy, Terminal } from "lucide-react";

interface SafeMarkdownProps {
  content: string;
}

export const SafeMarkdown: React.FC<SafeMarkdownProps> = ({ content }) => {
  // Split by code block fences (```)
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-3 text-sm leading-relaxed text-[#1C2024]">
      {parts.map((part, index) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          // It's a code block
          const lines = part.slice(3, -3).trim().split("\n");
          let language = "";
          let code = part.slice(3, -3);

          if (lines.length > 0 && lines[0].trim().length > 0 && !lines[0].includes(" ")) {
            language = lines[0].trim();
            code = lines.slice(1).join("\n");
          }

          return <CodeBlock key={index} code={code.trim()} language={language} />;
        }

        // Normal paragraph text
        return <FormattedParagraph key={index} text={part} />;
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

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-[#2D333B] bg-[#14171C] text-[#E6E8EB] shadow-xs">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#1C2128] border-b border-[#2D333B] text-[11px] text-[#8B93A0]">
        <div className="flex items-center gap-1.5 font-mono">
          <Terminal className="w-3.5 h-3.5 text-[#0B6E5F]" />
          <span>{language || "code"}</span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-white/10 text-white transition-colors cursor-pointer"
          title="Copy code to clipboard"
        >
          {copied ? (
            <>
              <Check className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-emerald-400 font-medium">Copied</span>
            </>
          ) : (
            <>
              <Copy className="w-3 h-3" />
              <span className="text-[10px]">Copy</span>
            </>
          )}
        </button>
      </div>

      <div className="p-3.5 overflow-x-auto text-xs font-mono leading-relaxed">
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((line, idx) => (
              <tr key={idx} className="hover:bg-white/[0.03]">
                <td className="pr-4 select-none text-right text-[#636A74] w-6 align-top">
                  {idx + 1}
                </td>
                <td className="whitespace-pre font-mono text-[#E6E8EB]">{line}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const FormattedParagraph: React.FC<{ text: string }> = ({ text }) => {
  if (!text.trim()) return null;

  // Split into paragraphs by double newlines
  const paragraphs = text.split(/\n\n+/);

  return (
    <>
      {paragraphs.map((para, pIdx) => {
        const trimmed = para.trim();
        if (!trimmed) return null;

        // Check if paragraph is a list
        const lines = trimmed.split("\n");
        const isBulletList = lines.every((l) => l.trim().startsWith("- ") || l.trim().startsWith("* "));
        const isNumberList = lines.every((l) => /^\d+\.\s/.test(l.trim()));

        if (isBulletList) {
          return (
            <ul key={pIdx} className="list-disc pl-5 space-y-1.5 my-2">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  <InlineFormatter text={l.trim().replace(/^[-*]\s+/, "")} />
                </li>
              ))}
            </ul>
          );
        }

        if (isNumberList) {
          return (
            <ol key={pIdx} className="list-decimal pl-5 space-y-1.5 my-2">
              {lines.map((l, lIdx) => (
                <li key={lIdx}>
                  <InlineFormatter text={l.trim().replace(/^\d+\.\s+/, "")} />
                </li>
              ))}
            </ol>
          );
        }

        return (
          <p key={pIdx} className="leading-relaxed">
            <InlineFormatter text={trimmed} />
          </p>
        );
      })}
    </>
  );
};

const InlineFormatter: React.FC<{ text: string }> = ({ text }) => {
  // Match inline code `code`, bold **bold**, and citation chips [File: ... Lines: ...]
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[File:[^\]]+\])/g);

  return (
    <>
      {tokens.map((token, idx) => {
        if (token.startsWith("`") && token.endsWith("`")) {
          return (
            <code
              key={idx}
              className="px-1.5 py-0.5 rounded-md bg-[#ECE9E3] text-[#1C2024] font-mono text-[12px] border border-[#DAD6CE]"
            >
              {token.slice(1, -1)}
            </code>
          );
        }

        if (token.startsWith("**") && token.endsWith("**")) {
          return (
            <strong key={idx} className="font-semibold text-[#1C2024]">
              {token.slice(2, -2)}
            </strong>
          );
        }

        if (token.startsWith("[File:") && token.endsWith("]")) {
          return (
            <span
              key={idx}
              className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md bg-[#E6F4F1] text-[#0B6E5F] font-mono text-[11px] font-semibold border border-[#BDE3DC]"
            >
              {token}
            </span>
          );
        }

        return <span key={idx}>{token}</span>;
      })}
    </>
  );
};

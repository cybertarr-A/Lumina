"use client";

import dynamic from "next/dynamic";
import { useEditorStore } from "@/lib/store";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full bg-[#1e1e2e] rounded-xl">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-slate-400 text-sm">Loading editor…</p>
      </div>
    </div>
  ),
});

interface SolidityEditorProps {
  value?: string;
  onChange?: (value: string) => void;
  readOnly?: boolean;
  height?: string;
  markers?: Array<{
    startLineNumber: number;
    startColumn: number;
    endLineNumber: number;
    endColumn: number;
    message: string;
    severity: number;
  }>;
}

const SOLIDITY_TOKENS = {
  keywords: [
    "pragma", "solidity", "contract", "interface", "library", "abstract",
    "function", "modifier", "event", "error", "struct", "enum", "mapping",
    "returns", "return", "public", "private", "internal", "external",
    "view", "pure", "payable", "nonpayable", "virtual", "override",
    "memory", "storage", "calldata", "immutable", "constant",
    "constructor", "fallback", "receive",
    "if", "else", "for", "while", "do", "break", "continue",
    "emit", "revert", "require", "assert",
    "new", "delete", "this", "super",
    "address", "uint", "int", "bool", "bytes", "string",
    "uint256", "uint128", "uint64", "uint32", "uint16", "uint8",
    "int256", "int128", "int64", "int32", "int16", "int8",
    "bytes32", "bytes16", "bytes8", "bytes4", "bytes1",
    "true", "false",
    "msg", "block", "tx", "abi",
    "import", "from", "as", "is",
  ],
};

export function SolidityEditor({
  value,
  onChange,
  readOnly = false,
  height = "100%",
  markers = [],
}: SolidityEditorProps) {
  const { sourceCode, setSourceCode } = useEditorStore();
  const editorValue = value !== undefined ? value : sourceCode;

  function handleEditorDidMount(editor: unknown, monaco: unknown) {
    const m = monaco as { editor: { setModelMarkers: Function }; MarkerSeverity: Record<string, number> };
    const ed = editor as { getModel: Function };

    // Register Solidity language basics if not already
    const monacoInstance = monaco as {
      languages: {
        register: Function;
        setMonarchTokensProvider: Function;
        registerCompletionItemProvider: Function;
        CompletionItemKind: Record<string, number>;
      };
    };

    monacoInstance.languages.register({ id: "solidity" });
    monacoInstance.languages.setMonarchTokensProvider("solidity", {
      keywords: SOLIDITY_TOKENS.keywords,
      tokenizer: {
        root: [
          [/\/\/.*$/, "comment"],
          [/\/\*/, "comment", "@comment"],
          [/"([^"\\]|\\.)*"/, "string"],
          [/'([^'\\]|\\.)*'/, "string"],
          [/0x[0-9a-fA-F]+/, "number.hex"],
          [/\d+(\.\d+)?/, "number"],
          [/[a-zA-Z_]\w*/, {
            cases: {
              "@keywords": "keyword",
              "@default": "identifier",
            },
          }],
        ],
        comment: [
          [/[^/*]+/, "comment"],
          [/\*\//, "comment", "@pop"],
          [/[/*]/, "comment"],
        ],
      },
    });

    // Completion provider for common patterns
    monacoInstance.languages.registerCompletionItemProvider("solidity", {
      provideCompletionItems: () => ({
        suggestions: [
          {
            label: "pragma",
            kind: monacoInstance.languages.CompletionItemKind.Keyword,
            insertText: "pragma solidity ^0.8.20;",
            documentation: "Specify Solidity version",
          },
          {
            label: "spdx",
            kind: monacoInstance.languages.CompletionItemKind.Snippet,
            insertText: "// SPDX-License-Identifier: MIT",
          },
          {
            label: "contract",
            kind: monacoInstance.languages.CompletionItemKind.Snippet,
            insertText: "contract ${1:MyContract} {\n    $0\n}",
            insertTextRules: 4,
          },
          {
            label: "function",
            kind: monacoInstance.languages.CompletionItemKind.Snippet,
            insertText: "function ${1:name}(${2:params}) ${3:external} returns (${4:type}) {\n    $0\n}",
            insertTextRules: 4,
          },
          {
            label: "event",
            kind: monacoInstance.languages.CompletionItemKind.Snippet,
            insertText: "event ${1:EventName}(${2:address indexed user, uint256 amount});",
            insertTextRules: 4,
          },
          {
            label: "error",
            kind: monacoInstance.languages.CompletionItemKind.Snippet,
            insertText: "error ${1:ErrorName}(${2:});",
            insertTextRules: 4,
          },
        ],
      }),
    });

    // Set error markers
    if (markers.length > 0) {
      const model = ed.getModel();
      if (model) {
        m.editor.setModelMarkers(model, "solidity", markers);
      }
    }
  }

  return (
    <div className="h-full w-full rounded-xl overflow-hidden border border-white/10">
      <MonacoEditor
        height={height}
        language="solidity"
        theme="vs-dark"
        value={editorValue}
        onChange={(val) => {
          if (onChange) onChange(val || "");
          else setSourceCode(val || "");
        }}
        options={{
          readOnly,
          fontSize: 14,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
          fontLigatures: true,
          lineNumbers: "on",
          minimap: { enabled: true, scale: 0.8 },
          wordWrap: "on",
          automaticLayout: true,
          tabSize: 4,
          scrollBeyondLastLine: false,
          renderLineHighlight: "all",
          bracketPairColorization: { enabled: true },
          formatOnPaste: true,
          smoothScrolling: true,
          cursorBlinking: "smooth",
          padding: { top: 16, bottom: 16 },
        }}
        onMount={handleEditorDidMount}
      />
    </div>
  );
}

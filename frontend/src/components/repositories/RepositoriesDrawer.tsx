"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  X,
  Search,
  FolderGit2,
  FileArchive,
  RefreshCw,
  Trash2,
  MessageSquare,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sparkles,
  LogOut,
  LogIn,
  Layers,
  FileCode,
} from "lucide-react";
import { RepositorySummary, IngestResponse } from "@/lib/types";
import {
  fetchUserRepositories,
  deleteRepository,
  reindexRepository,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface RepositoriesDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectRepo: (repo: IngestResponse) => void;
  onNewRepo: () => void;
  onOpenAuth: () => void;
}

export const RepositoriesDrawer: React.FC<RepositoriesDrawerProps> = ({
  isOpen,
  onClose,
  onSelectRepo,
  onNewRepo,
  onOpenAuth,
}) => {
  const { user, isAuthenticated, logout } = useAuth();
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [reindexingId, setReindexingId] = useState<string | null>(null);
  const [repoToDelete, setRepoToDelete] = useState<RepositorySummary | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const loadRepositories = () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    fetchUserRepositories()
      .then((data) => {
        setRepositories(data);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load repositories");
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    let active = true;
    if (isOpen && isAuthenticated) {
      fetchUserRepositories()
        .then((data) => {
          if (active) {
            setRepositories(data);
            setIsLoading(false);
          }
        })
        .catch((err: unknown) => {
          if (active) {
            setError(err instanceof Error ? err.message : "Failed to load repositories");
            setIsLoading(false);
          }
        });
    }
    return () => {
      active = false;
    };
  }, [isOpen, isAuthenticated, user]);


  const filteredRepos = useMemo(() => {
    if (!isAuthenticated) return [];
    if (!searchQuery.trim()) return repositories;
    const q = searchQuery.toLowerCase();
    return repositories.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.source_type.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    );
  }, [repositories, searchQuery, isAuthenticated]);

  const handleOpenChat = (repo: RepositorySummary) => {
    const ingestResp: IngestResponse = {
      repo_id: repo.repo_id,
      repo_name: repo.name,
      source_type: repo.source_type,
      status: repo.status,
      message: "Ready for questions",
    };
    onSelectRepo(ingestResp);
    onClose();
  };

  const handleReindex = async (repoId: string) => {
    try {
      setReindexingId(repoId);
      await reindexRepository(repoId);
      await loadRepositories();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Re-indexing failed");
    } finally {
      setReindexingId(null);
    }
  };

  const confirmDelete = async () => {
    if (!repoToDelete) return;
    try {
      setIsDeleting(true);
      await deleteRepository(repoToDelete.repo_id);
      setRepositories((prev) => prev.filter((r) => r.repo_id !== repoToDelete.repo_id));
      setRepoToDelete(null);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end animate-in fade-in duration-200">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
      />

      {/* Drawer Panel */}
      <div className="relative w-full sm:w-[480px] bg-white h-full shadow-2xl z-10 flex flex-col border-l border-[#E5E2DB]">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#F0EFEA] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[#0B6E5F] text-white flex items-center justify-center shadow-sm">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-base text-[#1C2024]">
                  My Repositories
                </h2>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#E6F4F1] text-[#0B6E5F]">
                  {repositories.length}
                </span>
              </div>
              <p className="text-xs text-[#636A74]">
                Manage indexed codebases and chat workspaces
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-[#636A74] hover:text-[#1C2024] hover:bg-[#F0EFEA] flex items-center justify-center transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Session Bar */}
        <div className="px-4 py-3 bg-[#FAF9F6] border-b border-[#F0EFEA] flex items-center justify-between text-xs">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-[#0B6E5F] text-white font-bold flex items-center justify-center text-xs">
                {user.name.charAt(0).toUpperCase()}
              </div>
              <div>
                <div className="font-semibold text-[#1C2024] flex items-center gap-1.5">
                  <span>{user.name}</span>
                  {user.is_guest && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-medium">
                      Guest
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-[#8C877D] truncate max-w-[200px]">
                  {user.email}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-[#636A74]">
              <Sparkles className="w-4 h-4 text-[#0B6E5F]" />
              <span>Browsing as anonymous session</span>
            </div>
          )}

          <div>
            {isAuthenticated ? (
              <button
                onClick={logout}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg border border-[#D0CFC8] bg-white text-[#636A74] hover:text-rose-600 hover:border-rose-300 transition-colors font-medium text-[11px]"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Log out</span>
              </button>
            ) : (
              <button
                onClick={() => {
                  onClose();
                  onOpenAuth();
                }}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#0B6E5F] text-white font-medium text-[11px] hover:bg-[#09584C] transition-colors"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Sign in</span>
              </button>
            )}
          </div>
        </div>

        {/* Search Bar */}
        <div className="p-4 border-b border-[#F0EFEA]">
          <div className="relative">
            <Search className="w-4 h-4 text-[#8C877D] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search repositories by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs rounded-xl border border-[#D0CFC8] bg-[#F7F6F3] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0B6E5F] transition-all"
            />
          </div>
        </div>

        {/* Repositories List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-12 text-[#636A74] space-y-2">
              <RefreshCw className="w-6 h-6 animate-spin text-[#0B6E5F]" />
              <span className="text-xs">Loading repositories...</span>
            </div>
          )}

          {/* Unauthenticated View */}
          {!isLoading && !isAuthenticated && (
            <div className="text-center py-12 px-4 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-[#0B6E5F]/10 text-[#0B6E5F] mx-auto flex items-center justify-center">
                <Sparkles className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-semibold text-sm text-[#1C2024]">
                  Sign in to view your repositories
                </h4>
                <p className="text-xs text-[#636A74] mt-1 max-w-xs mx-auto">
                  Repositories are isolated to your authenticated account or guest developer session.
                </p>
              </div>
              <div className="pt-2">
                <button
                  onClick={() => {
                    onOpenAuth();
                  }}
                  className="px-4 py-2 bg-[#0B6E5F] text-white rounded-xl text-xs font-semibold hover:bg-[#09584C] transition-all shadow-sm"
                >
                  Sign In / Create Account
                </button>
              </div>
            </div>
          )}

          {!isLoading && isAuthenticated && error && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-700 space-y-2">
              <div className="font-semibold flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4" />
                <span>Failed to fetch repositories</span>
              </div>
              <p>{error}</p>
              <button
                onClick={loadRepositories}
                className="px-3 py-1 bg-white border border-rose-300 rounded-lg text-rose-700 hover:bg-rose-100 font-medium"
              >
                Retry
              </button>
            </div>
          )}

          {!isLoading && isAuthenticated && !error && filteredRepos.length === 0 && (
            <div className="text-center py-12 px-4 space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-[#F0EFEA] text-[#8C877D] mx-auto flex items-center justify-center">
                <FileCode className="w-6 h-6" />
              </div>
              <div>
                <h4 className="font-semibold text-sm text-[#1C2024]">
                  {searchQuery ? "No matching repositories" : "No repositories indexed yet"}
                </h4>
                <p className="text-xs text-[#636A74] mt-1 max-w-xs mx-auto">
                  {searchQuery
                    ? "Try a different search term or clear the filter."
                    : "Upload a ZIP archive or paste a public Git URL to index your first codebase."}
                </p>
              </div>
              {!searchQuery && (
                <button
                  onClick={() => {
                    onClose();
                    onNewRepo();
                  }}
                  className="px-4 py-2 bg-[#0B6E5F] text-white rounded-xl text-xs font-semibold hover:bg-[#09584C] transition-all shadow-sm"
                >
                  Ingest Repository
                </button>
              )}
            </div>
          )}

          {!isLoading &&
            filteredRepos.map((repo) => {
              const isGit = repo.source_type === "git";
              const isReady = repo.status === "ready";
              const isProcessing = repo.status === "processing" || reindexingId === repo.repo_id;

              return (
                <div
                  key={repo.repo_id}
                  className="rounded-xl border border-[#E5E2DB] bg-[#FAF9F6] hover:bg-white hover:border-[#BDE3DC] p-4 transition-all shadow-sm hover:shadow group"
                >
                  {/* Card Title & Badges */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-white border border-[#E0DED7] flex items-center justify-center text-[#484F58]">
                        {isGit ? (
                          <FolderGit2 className="w-4 h-4 text-[#0B6E5F]" />
                        ) : (
                          <FileArchive className="w-4 h-4 text-[#B54708]" />
                        )}
                      </div>
                      <div>
                        <h4 className="font-semibold text-xs text-[#1C2024] group-hover:text-[#0B6E5F] transition-colors truncate max-w-[220px]">
                          {repo.name}
                        </h4>
                        <div className="flex items-center gap-1.5 text-[10px] text-[#8C877D]">
                          <span className="uppercase font-mono font-medium">
                            {repo.source_type}
                          </span>
                          <span>•</span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {new Date(repo.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <div>
                      {isReady && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-medium">
                          <CheckCircle2 className="w-3 h-3" />
                          Ready
                        </span>
                      )}
                      {isProcessing && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-medium">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          Indexing
                        </span>
                      )}
                      {repo.status === "failed" && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-medium">
                          <AlertTriangle className="w-3 h-3" />
                          Failed
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Metrics Bar */}
                  <div className="mt-3 grid grid-cols-3 gap-2 py-2 px-2.5 rounded-lg bg-white border border-[#F0EFEA] text-[11px] text-[#484F58]">
                    <div>
                      <div className="text-[10px] text-[#8C877D]">Files</div>
                      <div className="font-semibold text-[#1C2024]">
                        {repo.stats?.included_files ?? repo.stats?.discovered_files ?? 0}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-[#8C877D]">Total Lines</div>
                      <div className="font-semibold text-[#1C2024]">
                        {(repo.stats?.total_lines ?? 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-[#8C877D]">Size</div>
                      <div className="font-semibold text-[#1C2024]">
                        {repo.stats?.total_size_bytes
                          ? `${(repo.stats.total_size_bytes / 1024).toFixed(0)} KB`
                          : "N/A"}
                      </div>
                    </div>
                  </div>

                  {/* Actions Toolbar */}
                  <div className="mt-3 flex items-center justify-between gap-2 pt-2 border-t border-[#F0EFEA]">
                    <button
                      onClick={() => handleOpenChat(repo)}
                      disabled={!isReady}
                      className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-[#0B6E5F] hover:bg-[#09584C] text-white text-xs font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                    >
                      <MessageSquare className="w-3.5 h-3.5" />
                      <span>Open Chat</span>
                    </button>

                    <button
                      onClick={() => handleReindex(repo.repo_id)}
                      disabled={isProcessing}
                      title="Re-run indexing pipeline"
                      className="p-1.5 rounded-lg border border-[#D0CFC8] bg-white hover:bg-[#F0EFEA] text-[#636A74] hover:text-[#1C2024] transition-colors disabled:opacity-40"
                    >
                      <RefreshCw
                        className={`w-3.5 h-3.5 ${
                          reindexingId === repo.repo_id ? "animate-spin" : ""
                        }`}
                      />
                    </button>

                    <button
                      onClick={() => setRepoToDelete(repo)}
                      title="Delete repository and remove indexed files"
                      className="p-1.5 rounded-lg border border-[#D0CFC8] bg-white hover:bg-rose-50 text-[#636A74] hover:text-rose-600 hover:border-rose-300 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
        </div>

        {/* Drawer Bottom Bar */}
        <div className="p-4 border-t border-[#F0EFEA] bg-[#FAF9F6] flex items-center justify-between">
          <button
            onClick={() => {
              onClose();
              onNewRepo();
            }}
            className="w-full py-2 px-4 rounded-xl border border-[#D0CFC8] bg-white hover:bg-[#F0EFEA] text-[#1C2024] text-xs font-semibold transition-all shadow-sm flex items-center justify-center gap-2"
          >
            <span>+ Ingest Another Repository</span>
          </button>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {repoToDelete && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-[#E5E2DB] space-y-4 animate-in zoom-in-95 duration-150">
            <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
              <Trash2 className="w-5 h-5" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="font-semibold text-sm text-[#1C2024]">
                Delete &quot;{repoToDelete.name}&quot;?
              </h3>
              <p className="text-xs text-[#636A74] leading-relaxed">
                This will permanently erase all extracted source files, BM25 indices, and vector embeddings from storage.
              </p>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                onClick={() => setRepoToDelete(null)}
                disabled={isDeleting}
                className="flex-1 py-2 rounded-xl border border-[#D0CFC8] text-xs font-semibold text-[#636A74] hover:bg-[#F0EFEA] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                className="flex-1 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold transition-colors shadow-sm disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {isDeleting && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

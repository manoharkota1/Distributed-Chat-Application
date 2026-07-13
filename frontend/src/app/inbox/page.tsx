'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api/client';
import { wsClient } from '@/lib/ws/socket';
import { useAppStore, Conversation, Message } from '@/lib/store';
import { useAuth } from '@/hooks/useAuth';

/**
 * Inbox page — sidebar with conversation list + chat view.
 * This is the main authenticated view of the application.
 */
export default function InboxPage() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const {
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversation,
    messages,
    setMessages,
    addMessage,
    reconcileMessage,
    typingUsers,
    setTypingUser,
  } = useAppStore();

  const [messageInput, setMessageInput] = useState('');
  const [showNewChat, setShowNewChat] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{
    id: string;
    email: string;
    display_name: string;
  }>>([]);
  const [loading, setLoading] = useState(true);

  // Load conversations
  const loadConversations = useCallback(async () => {
    const res = await api.get<{
      conversations: Conversation[];
      total: number;
    }>('/conversations');
    if (res.data) {
      setConversations(res.data.conversations);
    }
    setLoading(false);
  }, [setConversations]);

  // Load messages for active conversation
  const loadMessages = useCallback(async (convoId: string) => {
    const res = await api.get<{
      messages: Message[];
      next_cursor: string | null;
      has_more: boolean;
    }>(`/conversations/${convoId}/messages?limit=50`);
    if (res.data) {
      setMessages(convoId, [...res.data.messages].reverse());
    }
  }, [setMessages]);



  // Load conversations on mount
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated, loadConversations]);

  // WebSocket event handlers
  useEffect(() => {
    const unsubs = [
      wsClient.on('message.new', (payload) => {
        const convoId = payload.conversation_id as string;
        const tempId = payload.client_temp_id as string | undefined;
        const message: Message = {
          id: payload.id as string,
          conversation_id: convoId,
          sender_id: payload.sender_id as string,
          content: payload.content as string,
          created_at: payload.created_at as string,
        };
        if (tempId) {
          reconcileMessage(convoId, tempId, message);
        } else {
          addMessage(convoId, message);
        }
      }),

      wsClient.on('message.ack', (payload) => {
        const convoId = payload.conversation_id as string;
        const tempId = payload.client_temp_id as string;
        if (tempId) {
          reconcileMessage(convoId, tempId, {
            id: payload.id as string,
            conversation_id: convoId,
            sender_id: payload.sender_id as string,
            content: payload.content as string,
            created_at: payload.created_at as string,
          });
        }
      }),

      wsClient.on('typing.update', (payload) => {
        const convoId = payload.conversation_id as string;
        const userId = payload.user_id as string;
        const isTyping = payload.is_typing as boolean;
        if (userId !== user?.id) {
          setTypingUser(convoId, userId, isTyping);
        }
      }),
    ];

    return () => unsubs.forEach((unsub) => unsub());
  }, [user?.id, addMessage, reconcileMessage, setTypingUser]);

  // Load messages when conversation changes
  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    }
  }, [activeConversationId, loadMessages]);

  // Send message
  const handleSendMessage = useCallback(() => {
    if (!messageInput.trim() || !activeConversationId || !user) return;

    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substring(2)}`;

    // Optimistic UI — add message immediately
    addMessage(activeConversationId, {
      id: tempId,
      conversation_id: activeConversationId,
      sender_id: user.id,
      sender_display_name: user.display_name,
      content: messageInput.trim(),
      created_at: new Date().toISOString(),
      client_temp_id: tempId,
      pending: true,
    });

    // Send via WebSocket
    wsClient.send('message.send', {
      conversation_id: activeConversationId,
      content: messageInput.trim(),
      client_temp_id: tempId,
    });

    setMessageInput('');
  }, [messageInput, activeConversationId, user, addMessage]);

  // Search users for new conversation
  const handleSearch = useCallback(async (query: string) => {
    setSearchQuery(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    const res = await api.get<Array<{
      id: string;
      email: string;
      display_name: string;
    }>>(`/users/search?q=${encodeURIComponent(query)}`);
    if (res.data) {
      setSearchResults(res.data.filter((u) => u.id !== user?.id));
    }
  }, [user?.id]);

  // Create direct conversation
  const handleStartChat = useCallback(async (userId: string) => {
    const res = await api.post<{ id: string }>('/conversations', {
      type: 'direct',
      member_ids: [userId],
    });
    if (res.data) {
      setActiveConversation(res.data.id);
      setShowNewChat(false);
      setSearchQuery('');
      setSearchResults([]);
      await loadConversations();
    }
  }, [setActiveConversation, loadConversations]);

  const activeConversation = conversations.find((c) => c.id === activeConversationId);
  const activeMessages = messages[activeConversationId || ''] || [];
  const activeTyping = typingUsers[activeConversationId || ''] || [];

  const getConversationName = (convo: Conversation) => {
    if (convo.name) return convo.name;
    const otherMember = convo.members.find((m) => m.user_id !== user?.id);
    return otherMember?.display_name || 'Unknown';
  };

  const getInitials = (name: string) => {
    return name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2);
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (!isAuthenticated) return null;

  return (
    <div>
      {/* Navbar */}
      <nav className="navbar">
        <span className="navbar-brand"><span className="app-mark">DC</span> Distributed Chat</span>
        <div className="navbar-links">
          <Link href="/profile" className="btn btn-ghost">Profile</Link>
          <Link href="/sessions" className="btn btn-ghost">Sessions</Link>
          <button onClick={logout} className="btn btn-ghost">
            Logout
          </button>
        </div>
      </nav>

      {/* Main Layout */}
      <main className="app-layout">
        {/* Sidebar */}
        <div className="sidebar">
          <div className="sidebar-header">
            <h1>Messages</h1>
            <button
              className="btn btn-secondary"
              onClick={() => setShowNewChat(!showNewChat)}
              aria-expanded={showNewChat}
              aria-controls="new-chat-panel"
            >
              {showNewChat ? 'Close' : 'New chat'}
            </button>
          </div>

          {/* New Chat Search */}
          {showNewChat && (
            <div className="new-chat-panel" id="new-chat-panel">
              <input
                type="text"
                className="input"
                placeholder="Search users by email or name..."
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                autoFocus
              />
              {searchResults.length > 0 && (
                <div className="search-results" role="listbox" aria-label="People matching your search">
                  {searchResults.map((u) => (
                    <button
                      key={u.id}
                      className="conversation-item"
                      onClick={() => handleStartChat(u.id)}
                      role="option"
                      aria-selected={false}
                    >
                      <div className="conversation-avatar">
                        {getInitials(u.display_name)}
                      </div>
                      <div className="conversation-info">
                        <div className="conversation-name">{u.display_name}</div>
                        <div className="conversation-preview">{u.email}</div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Conversation List */}
          <div className="conversation-list">
            {loading ? (
              <div className="loading-container">
                <div className="loading-spinner" />
              </div>
            ) : conversations.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✦</div>
                <h3>No conversations yet</h3>
                <p>Start a new conversation to begin chatting</p>
              </div>
            ) : (
              conversations.map((convo) => (
                <button
                  key={convo.id}
                  className={`conversation-item ${
                    convo.id === activeConversationId ? 'active' : ''
                  }`}
                  onClick={() => setActiveConversation(convo.id)}
                  aria-pressed={convo.id === activeConversationId}
                >
                  <div className="conversation-avatar">
                    {getInitials(getConversationName(convo))}
                  </div>
                  <div className="conversation-info">
                    <div className="conversation-name">
                      {getConversationName(convo)}
                    </div>
                    <div className="conversation-preview">
                      {convo.last_message?.content || 'No messages yet'}
                    </div>
                  </div>
                  <div className="conversation-meta">
                    {convo.last_message && (
                      <span className="conversation-time">
                        {formatTime(convo.last_message.created_at)}
                      </span>
                    )}
                    {convo.unread_count > 0 && (
                      <span className="unread-badge">{convo.unread_count}</span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat Area */}
        <div className="main-content">
          {activeConversation ? (
            <>
              {/* Chat Header */}
              <div className="chat-header">
                <div className="conversation-avatar">
                  {getInitials(getConversationName(activeConversation))}
                </div>
                <div className="chat-header-info">
                  <h2>{getConversationName(activeConversation)}</h2>
                  <span className="status">
                    {activeConversation.type === 'group'
                      ? `${activeConversation.members.length} members`
                      : activeConversation.members.find((m) => m.user_id !== user?.id)?.is_online
                        ? <><span className="status-dot online" />Online</>
                        : <><span className="status-dot" />Offline</>}
                  </span>
                </div>
              </div>

              {/* Messages */}
              <div className="chat-messages">
                {activeMessages.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">✦</div>
                    <h3>Start the conversation</h3>
                    <p>Send a message to get things going</p>
                  </div>
                ) : (
                  activeMessages.map((msg) => {
                    const isSent = msg.sender_id === user?.id;
                    return (
                      <div
                        key={msg.id}
                        className={`message-group ${isSent ? 'sent' : 'received'}`}
                      >
                        {!isSent && activeConversation.type === 'group' && (
                          <div className="message-sender">
                            {msg.sender_display_name || 'Unknown'}
                          </div>
                        )}
                        <div
                          className={`message-bubble ${isSent ? 'sent' : 'received'} ${
                            msg.pending ? 'pending' : ''
                          }`}
                        >
                          {msg.content}
                        </div>
                        <div className="message-time">
                          {formatTime(msg.created_at)}
                          {msg.pending && ' · Sending...'}
                        </div>
                      </div>
                    );
                  })
                )}

                {/* Typing Indicator */}
                {activeTyping.length > 0 && (
                  <div className="typing-indicator">
                    <div className="typing-dots">
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                    </div>
                    <span>
                      {activeTyping.length === 1
                        ? 'Someone is typing...'
                        : `${activeTyping.length} people are typing...`}
                    </span>
                  </div>
                )}
              </div>

              {/* Input */}
              <div className="chat-input-container">
                <div className="chat-input-wrapper">
                  <textarea
                    className="chat-input"
                    placeholder="Type a message..."
                    value={messageInput}
                    onChange={(e) => {
                      setMessageInput(e.target.value);
                      wsClient.send('typing.start', {
                        conversation_id: activeConversationId,
                      });
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    rows={1}
                  />
                  <button
                    className="send-button"
                    onClick={handleSendMessage}
                    disabled={!messageInput.trim()}
                    aria-label="Send message"
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="m4 12 15-8-4 16-4-6-7-2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
                    </svg>
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">✦</div>
              <h3>Select a conversation</h3>
              <p>Choose a conversation from the sidebar or start a new one</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

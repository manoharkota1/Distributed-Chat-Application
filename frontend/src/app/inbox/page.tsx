'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
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
    updateConversation,
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

  const [chatType, setChatType] = useState<'direct' | 'group'>('direct');
  const [groupName, setGroupName] = useState('');
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [showGroupDetails, setShowGroupDetails] = useState(false);
  const [groupSearchQuery, setGroupSearchQuery] = useState('');
  const [groupSearchResults, setGroupSearchResults] = useState<Array<{
    id: string;
    email: string;
    display_name: string;
  }>>([]);

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
      const msgList = [...res.data.messages].reverse();
      setMessages(convoId, msgList);
      updateConversation(convoId, { unread_count: 0 });
      if (msgList.length > 0) {
        const latestMsg = msgList[msgList.length - 1];
        wsClient.send('read.update', {
          conversation_id: convoId,
          message_id: latestMsg.id,
        });
      }
    }
  }, [setMessages, updateConversation]);



  const typingTimeoutsRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const isTypingRef = useRef(false);
  const typingStopTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleTyping = useCallback(() => {
    if (!activeConversationId) return;

    if (!isTypingRef.current) {
      isTypingRef.current = true;
      wsClient.send('typing.start', {
        conversation_id: activeConversationId,
      });
    }

    if (typingStopTimeoutRef.current) {
      clearTimeout(typingStopTimeoutRef.current);
    }

    typingStopTimeoutRef.current = setTimeout(() => {
      if (isTypingRef.current && activeConversationId) {
        wsClient.send('typing.stop', {
          conversation_id: activeConversationId,
        });
        isTypingRef.current = false;
      }
    }, 3000);
  }, [activeConversationId]);

  // Load conversations on mount
  useEffect(() => {
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated, loadConversations]);

  // WebSocket event handlers
  useEffect(() => {
    const unsubs = [
      wsClient.on('connect', () => {
        console.log('[WS] Reconnected — reloading data');
        loadConversations();
        const activeId = useAppStore.getState().activeConversationId;
        if (activeId) {
          loadMessages(activeId);
        }
      }),

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

        const isMyMessage = payload.sender_id === user?.id;

        if (isMyMessage && tempId) {
          reconcileMessage(convoId, tempId, message);
        } else {
          addMessage(convoId, message);
        }

        // Real-time unread counts and sidebar message previews
        const currentConvos = useAppStore.getState().conversations;
        const convo = currentConvos.find((c) => c.id === convoId);
        if (convo) {
          const isCurrentlyActive = convoId === useAppStore.getState().activeConversationId;
          const shouldIncrement = !isCurrentlyActive && !isMyMessage;
          updateConversation(convoId, {
            last_message: {
              id: message.id,
              content: message.content,
              sender_id: message.sender_id,
              created_at: message.created_at,
            },
            unread_count: shouldIncrement ? convo.unread_count + 1 : 0,
          });

          if (isCurrentlyActive) {
            wsClient.send('read.update', {
              conversation_id: convoId,
              message_id: message.id,
            });
          }
        } else {
          loadConversations();
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

      wsClient.on('read.receipt', (payload) => {
        const convoId = payload.conversation_id as string;
        const userId = payload.user_id as string;
        if (userId === useAppStore.getState().user?.id) {
          updateConversation(convoId, { unread_count: 0 });
        }
      }),

      wsClient.on('conversation.update', (payload) => {
        const activeId = useAppStore.getState().activeConversationId;
        const currentUser = useAppStore.getState().user;
        const isTargetRemovedUser = payload.action === 'member_removed' && payload.user_id === currentUser?.id;

        if (isTargetRemovedUser) {
          if (activeId === payload.conversation_id) {
            setActiveConversation(null);
            setShowGroupDetails(false);
          }
        }

        loadConversations();

        if (activeId && activeId === payload.conversation_id && !isTargetRemovedUser) {
          loadMessages(activeId);
        }
      }),

      wsClient.on('typing.update', (payload) => {
        const convoId = payload.conversation_id as string;
        const userId = payload.user_id as string;
        const isTyping = payload.is_typing as boolean;
        if (userId !== user?.id) {
          setTypingUser(convoId, userId, isTyping);

          // Auto-expire typing indicator after 5 seconds of inactivity
          const timeoutKey = `${convoId}:${userId}`;
          if (typingTimeoutsRef.current[timeoutKey]) {
            clearTimeout(typingTimeoutsRef.current[timeoutKey]);
          }

          if (isTyping) {
            typingTimeoutsRef.current[timeoutKey] = setTimeout(() => {
              setTypingUser(convoId, userId, false);
              delete typingTimeoutsRef.current[timeoutKey];
            }, 5000);
          } else {
            delete typingTimeoutsRef.current[timeoutKey];
          }
        }
      }),
    ];

    return () => {
      unsubs.forEach((unsub) => unsub());
      Object.values(typingTimeoutsRef.current).forEach(clearTimeout);
      typingTimeoutsRef.current = {};
    };
  }, [user?.id, addMessage, reconcileMessage, setTypingUser, updateConversation, loadConversations, loadMessages]);

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

  // Create group conversation
  const handleCreateGroup = useCallback(async () => {
    if (!groupName.trim() || selectedMemberIds.length === 0) return;
    const res = await api.post<{ id: string }>('/conversations', {
      type: 'group',
      name: groupName.trim(),
      member_ids: selectedMemberIds,
    });
    if (res.data) {
      setActiveConversation(res.data.id);
      setShowNewChat(false);
      setGroupName('');
      setSelectedMemberIds([]);
      await loadConversations();
    }
  }, [groupName, selectedMemberIds, setActiveConversation, loadConversations]);

  // Search users for existing group
  const handleSearchForGroup = useCallback(async (query: string) => {
    setGroupSearchQuery(query);
    if (query.length < 2) {
      setGroupSearchResults([]);
      return;
    }
    const res = await api.get<Array<{
      id: string;
      email: string;
      display_name: string;
    }>>(`/users/search?q=${encodeURIComponent(query)}`);
    if (res.data && activeConversation) {
      const existingMemberIds = activeConversation.members.map((m) => m.user_id);
      setGroupSearchResults(res.data.filter((u) => !existingMemberIds.includes(u.id)));
    }
  }, [activeConversation]);

  // Add member to active group
  const handleAddMember = useCallback(async (userIdToAdd: string) => {
    if (!activeConversationId) return;
    const res = await api.post(`/conversations/${activeConversationId}/members`, {
      user_id: userIdToAdd,
    });
    if (!res.error) {
      setGroupSearchQuery('');
      setGroupSearchResults([]);
      await loadConversations();
      await loadMessages(activeConversationId);
    }
  }, [activeConversationId, loadConversations, loadMessages]);

  // Remove member from active group
  const handleRemoveMember = useCallback(async (userIdToRemove: string) => {
    if (!activeConversationId) return;
    const res = await api.delete(`/conversations/${activeConversationId}/members/${userIdToRemove}`);
    if (!res.error) {
      await loadConversations();
      await loadMessages(activeConversationId);
    }
  }, [activeConversationId, loadConversations, loadMessages]);

  // Leave active group
  const handleLeaveGroup = useCallback(async () => {
    if (!activeConversationId || !user) return;
    const res = await api.delete(`/conversations/${activeConversationId}/members/${user.id}`);
    if (!res.error) {
      setActiveConversation(null);
      setShowGroupDetails(false);
      await loadConversations();
    }
  }, [activeConversationId, user, setActiveConversation, loadConversations]);
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
            <div className="new-chat-panel" id="new-chat-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--line)', paddingBottom: '8px' }}>
                <button
                  type="button"
                  className={`btn ${chatType === 'direct' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ flex: 1, minHeight: '32px', padding: '4px 8px', fontSize: '12px' }}
                  onClick={() => { setChatType('direct'); setSelectedMemberIds([]); }}
                >
                  Direct Message
                </button>
                <button
                  type="button"
                  className={`btn ${chatType === 'group' ? 'btn-primary' : 'btn-ghost'}`}
                  style={{ flex: 1, minHeight: '32px', padding: '4px 8px', fontSize: '12px' }}
                  onClick={() => setChatType('group')}
                >
                  Group Chat
                </button>
              </div>

              {chatType === 'group' && (
                <input
                  type="text"
                  className="input"
                  placeholder="Group name..."
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  style={{ width: '100%', marginBottom: '4px' }}
                />
              )}

              <input
                type="text"
                className="input"
                placeholder={chatType === 'direct' ? "Search users by email or name..." : "Add members..."}
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                autoFocus
              />

              {chatType === 'group' && selectedMemberIds.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', margin: '4px 0' }}>
                  {selectedMemberIds.map((memberId) => {
                    const u = searchResults.find(r => r.id === memberId);
                    const displayName = u ? u.display_name : memberId.slice(0, 8);
                    return (
                      <span
                        key={memberId}
                        style={{
                          background: 'var(--accent-soft)',
                          color: 'var(--accent)',
                          padding: '4px 8px',
                          borderRadius: '12px',
                          fontSize: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontWeight: 600,
                        }}
                      >
                        {displayName}
                        <button
                          type="button"
                          style={{ border: 'none', background: 'none', color: 'inherit', cursor: 'pointer', padding: 0, fontSize: '10px' }}
                          onClick={() => setSelectedMemberIds(prev => prev.filter(id => id !== memberId))}
                        >
                          ✕
                        </button>
                      </span>
                    );
                  })}
                </div>
              )}

              {searchResults.length > 0 && (
                <div className="search-results" role="listbox" aria-label="People matching your search" style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {searchResults.map((u) => {
                    const isSelected = selectedMemberIds.includes(u.id);
                    return (
                      <button
                        key={u.id}
                        className={`conversation-item ${isSelected ? 'active' : ''}`}
                        onClick={() => {
                          if (chatType === 'direct') {
                            handleStartChat(u.id);
                          } else {
                            if (isSelected) {
                              setSelectedMemberIds(prev => prev.filter(id => id !== u.id));
                            } else {
                              setSelectedMemberIds(prev => [...prev, u.id]);
                            }
                          }
                        }}
                        role="option"
                        aria-selected={isSelected}
                      >
                        <div className="conversation-avatar">
                          {getInitials(u.display_name)}
                        </div>
                        <div className="conversation-info" style={{ display: 'block' }}>
                          <div className="conversation-name">{u.display_name}</div>
                          <div className="conversation-preview">{u.email}</div>
                        </div>
                        {chatType === 'group' && (
                          <div style={{ marginLeft: 'auto', fontWeight: 'bold', color: isSelected ? 'var(--accent)' : 'var(--ink-faint)' }}>
                            {isSelected ? '✓' : '+'}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {chatType === 'group' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleCreateGroup}
                  disabled={!groupName.trim() || selectedMemberIds.length === 0}
                  style={{ width: '100%', marginTop: '6px' }}
                >
                  Create Group ({selectedMemberIds.length} members)
                </button>
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
        <div className="main-content" style={{ display: 'flex', position: 'relative' }}>
          {activeConversation ? (
            <div style={{ display: 'flex', flex: 1, height: '100%', overflow: 'hidden' }}>
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, height: '100%', borderRight: showGroupDetails && activeConversation.type === 'group' ? '1px solid var(--line)' : 'none' }}>
                {/* Chat Header */}
                <div className="chat-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
                  {activeConversation.type === 'group' && (
                    <button
                      type="button"
                      className={`btn ${showGroupDetails ? 'btn-primary' : 'btn-secondary'}`}
                      style={{ minHeight: '32px', padding: '6px 12px', fontSize: '13px' }}
                      onClick={() => setShowGroupDetails(!showGroupDetails)}
                    >
                      {showGroupDetails ? 'Hide Members' : 'Manage Group'}
                    </button>
                  )}
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
                        handleTyping();
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
              </div>

              {/* Group Details Sidebar */}
              {showGroupDetails && activeConversation.type === 'group' && (
                <div style={{ width: '280px', minWidth: '280px', display: 'flex', flexDirection: 'column', background: 'var(--surface)', height: '100%', overflowY: 'auto', padding: '20px', borderLeft: '1px solid var(--line)' }}>
                  <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: 700 }}>Group Members</h3>
                  
                  {/* Add Member Search */}
                  <div style={{ marginBottom: '20px' }}>
                    <input
                      type="text"
                      className="input"
                      placeholder="Add member by email/name..."
                      value={groupSearchQuery}
                      onChange={(e) => handleSearchForGroup(e.target.value)}
                      style={{ fontSize: '13px', width: '100%', padding: '8px' }}
                    />
                    {groupSearchResults.length > 0 && (
                      <div className="search-results" style={{ border: '1px solid var(--line)', borderRadius: '8px', marginTop: '6px', maxHeight: '150px', overflowY: 'auto', background: 'var(--surface-subtle)' }}>
                        {groupSearchResults.map((u) => (
                          <button
                            key={u.id}
                            type="button"
                            onClick={() => handleAddMember(u.id)}
                            style={{ display: 'flex', width: '100%', padding: '8px', border: 'none', background: 'none', cursor: 'pointer', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--line)', textAlign: 'left' }}
                          >
                            <div className="conversation-avatar" style={{ width: '24px', height: '24px', fontSize: '10px' }}>
                              {getInitials(u.display_name)}
                            </div>
                            <div style={{ flex: 1, overflow: 'hidden' }}>
                              <div style={{ fontSize: '12px', fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{u.display_name}</div>
                            </div>
                            <span style={{ fontSize: '14px', color: 'var(--accent)', fontWeight: 'bold' }}>+</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Members List */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1 }}>
                    {activeConversation.members.map((member) => (
                      <div key={member.user_id} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px 0' }}>
                        <div className="conversation-avatar" style={{ width: '32px', height: '32px', fontSize: '12px' }}>
                          {getInitials(member.display_name)}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: '13px', fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                            {member.display_name}
                          </div>
                          <span style={{ fontSize: '10px', color: member.is_online ? 'var(--success)' : 'var(--ink-faint)' }}>
                            {member.is_online ? 'Online' : 'Offline'}
                          </span>
                        </div>
                        {member.user_id !== user?.id && (
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => handleRemoveMember(member.user_id)}
                            style={{ padding: '2px 6px', minHeight: '24px', fontSize: '11px', color: 'var(--danger)' }}
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Leave Group Button */}
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={handleLeaveGroup}
                    style={{ width: '100%', marginTop: '20px', minHeight: '36px', fontSize: '13px' }}
                  >
                    Leave Group
                  </button>
                </div>
              )}
            </div>
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

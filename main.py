import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, doc, getDoc, addDoc, setDoc, updateDoc, deleteDoc, onSnapshot, collection, query, where, orderBy, serverTimestamp } from 'firebase/firestore';

// Main App component
const App = () => {
    const [activeTab, setActiveTab] = useState('mood'); // 'mood', 'journal', 'chat'
    const [mood, setMood] = useState('');
    const [journalEntry, setJournalEntry] = useState('');
    const [chatInput, setChatInput] = useState('');
    const [chatHistory, setChatHistory] = useState([]);
    const [moodEntries, setMoodEntries] = useState([]);
    const [journalEntries, setJournalEntries] = useState([]);
    const [loadingChat, setLoadingChat] = useState(false);
    const [loadingData, setLoadingData] = useState(true);
    const [userId, setUserId] = useState(null);
    const [firebaseDb, setFirebaseDb] = useState(null);
    const [firebaseAuth, setFirebaseAuth] = useState(null);
    const chatContainerRef = useRef(null);
    const [showConfirmation, setShowConfirmation] = useState(false);
    const [entryToDelete, setEntryToDelete] = useState(null);
    const [deleteType, setDeleteType] = useState(''); // 'mood' or 'journal'

    // Firebase initialization and authentication
    useEffect(() => {
        const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
        const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};

        try {
            const app = initializeApp(firebaseConfig);
            const db = getFirestore(app);
            const auth = getAuth(app);
            setFirebaseDb(db);
            setFirebaseAuth(auth);

            const unsubscribe = onAuthStateChanged(auth, async (user) => {
                if (user) {
                    setUserId(user.uid);
                } else {
                    // Sign in anonymously if no user is logged in
                    try {
                        if (typeof __initial_auth_token !== 'undefined') {
                            await signInWithCustomToken(auth, __initial_auth_token);
                        } else {
                            await signInAnonymously(auth);
                        }
                    } catch (error) {
                        console.error("Error signing in:", error);
                    }
                }
                setLoadingData(false);
            });

            return () => unsubscribe();
        } catch (error) {
            console.error("Error initializing Firebase:", error);
            setLoadingData(false);
        }
    }, []);

    // Fetch data from Firestore
    useEffect(() => {
        if (firebaseDb && userId) {
            // Listen for mood entries
            const moodQuery = query(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/moodEntries`));
            const unsubscribeMood = onSnapshot(moodQuery, (snapshot) => {
                const entries = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
                // Sort mood entries by timestamp in descending order
                entries.sort((a, b) => (b.timestamp?.toDate() || 0) - (a.timestamp?.toDate() || 0));
                setMoodEntries(entries);
            }, (error) => {
                console.error("Error fetching mood entries:", error);
            });

            // Listen for journal entries
            const journalQuery = query(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/journalEntries`));
            const unsubscribeJournal = onSnapshot(journalQuery, (snapshot) => {
                const entries = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
                // Sort journal entries by timestamp in descending order
                entries.sort((a, b) => (b.timestamp?.toDate() || 0) - (a.timestamp?.toDate() || 0));
                setJournalEntries(entries);
            }, (error) => {
                console.error("Error fetching journal entries:", error);
            });

            // Listen for chat history
            const chatQuery = query(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/chatHistory`));
            const unsubscribeChat = onSnapshot(chatQuery, (snapshot) => {
                const history = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
                // Sort chat history by timestamp in ascending order
                history.sort((a, b) => (a.timestamp?.toDate() || 0) - (b.timestamp?.toDate() || 0));
                setChatHistory(history);
            }, (error) => {
                console.error("Error fetching chat history:", error);
            });

            return () => {
                unsubscribeMood();
                unsubscribeJournal();
                unsubscribeChat();
            };
        }
    }, [firebaseDb, userId]);

    // Scroll to bottom of chat
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [chatHistory]);

    // Handle mood submission
    const handleMoodSubmit = async () => {
        if (!mood || !firebaseDb || !userId) return;

        try {
            await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/moodEntries`), {
                mood: mood,
                timestamp: serverTimestamp(),
                userId: userId,
            });
            setMood('');
        } catch (e) {
            console.error("Error adding mood entry: ", e);
        }
    };

    // Handle journal submission
    const handleJournalSubmit = async () => {
        if (!journalEntry.trim() || !firebaseDb || !userId) return;

        try {
            await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/journalEntries`), {
                content: journalEntry,
                timestamp: serverTimestamp(),
                userId: userId,
            });
            setJournalEntry('');
        } catch (e) {
            console.error("Error adding journal entry: ", e);
        }
    };

    // Handle chat message submission
    const handleChatSubmit = async (e) => {
        e.preventDefault();
        if (!chatInput.trim() || loadingChat || !firebaseDb || !userId) return;

        const userMessage = { role: 'user', text: chatInput, timestamp: serverTimestamp() };
        setChatHistory(prev => [...prev, userMessage]);
        await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/chatHistory`), userMessage);
        setChatInput('');
        setLoadingChat(true);

        try {
            const prompt = chatInput;
            let currentChatHistory = [...chatHistory, userMessage].map(msg => ({
                role: msg.role,
                parts: [{ text: msg.text }]
            }));

            const payload = { contents: currentChatHistory };
            const apiKey = ""; // Canvas will provide this
            const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`;

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (result.candidates && result.candidates.length > 0 &&
                result.candidates[0].content && result.candidates[0].content.parts &&
                result.candidates[0].content.parts.length > 0) {
                const aiResponseText = result.candidates[0].content.parts[0].text;
                const aiMessage = { role: 'model', text: aiResponseText, timestamp: serverTimestamp() };
                setChatHistory(prev => [...prev, aiMessage]);
                await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/chatHistory`), aiMessage);
            } else {
                const errorMessage = "Sorry, I couldn't generate a response. Please try again.";
                const aiMessage = { role: 'model', text: errorMessage, timestamp: serverTimestamp() };
                setChatHistory(prev => [...prev, aiMessage]);
                await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/chatHistory`), aiMessage);
                console.error("Unexpected API response structure:", result);
            }
        } catch (error) {
            console.error("Error communicating with AI chatbot:", error);
            const errorMessage = "There was an error connecting to the AI. Please check your network and try again.";
            const aiMessage = { role: 'model', text: errorMessage, timestamp: serverTimestamp() };
            setChatHistory(prev => [...prev, aiMessage]);
            await addDoc(collection(firebaseDb, `artifacts/${__app_id}/users/${userId}/chatHistory`), aiMessage);
        } finally {
            setLoadingChat(false);
        }
    };

    // Function to show confirmation dialog
    const confirmDelete = (id, type) => {
        setEntryToDelete({ id, type });
        setDeleteType(type);
        setShowConfirmation(true);
    };

    // Function to handle deletion
    const handleDelete = async () => {
        if (!entryToDelete || !firebaseDb || !userId) return;

        const { id, type } = entryToDelete;
        let collectionPath = '';
        if (type === 'mood') {
            collectionPath = `artifacts/${__app_id}/users/${userId}/moodEntries`;
        } else if (type === 'journal') {
            collectionPath = `artifacts/${__app_id}/users/${userId}/journalEntries`;
        }

        try {
            await deleteDoc(doc(firebaseDb, collectionPath, id));
            console.log(`${type} entry deleted successfully!`);
        } catch (e) {
            console.error(`Error deleting ${type} entry: `, e);
        } finally {
            setShowConfirmation(false);
            setEntryToDelete(null);
            setDeleteType('');
        }
    };

    // Format timestamp for display
    const formatTimestamp = (timestamp) => {
        if (!timestamp) return 'N/A';
        const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
        return date.toLocaleString();
    };

    if (loadingData) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-800 dark:text-gray-200">
                <div className="text-xl font-semibold">Loading app...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-purple-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 text-gray-800 dark:text-gray-200 font-inter p-4 sm:p-6 lg:p-8">
            <div className="max-w-4xl mx-auto bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="p-6 bg-gradient-to-r from-purple-600 to-indigo-700 text-white text-center rounded-t-xl">
                    <h1 className="text-3xl sm:text-4xl font-bold mb-2">My Well-being Hub</h1>
                    <p className="text-lg sm:text-xl opacity-90">Track your mood, journal, and chat with AI.</p>
                    {userId && (
                        <p className="text-sm mt-2 opacity-80">User ID: {userId}</p>
                    )}
                </div>

                {/* Navigation Tabs */}
                <div className="flex justify-around bg-gray-100 dark:bg-gray-700 p-3 border-b border-gray-200 dark:border-gray-600">
                    <button
                        onClick={() => setActiveTab('mood')}
                        className={`py-2 px-4 rounded-lg font-medium transition-all duration-300 ${activeTab === 'mood' ? 'bg-purple-500 text-white shadow-md' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
                    >
                        <i className="fas fa-smile mr-2"></i>Mood Tracker
                    </button>
                    <button
                        onClick={() => setActiveTab('journal')}
                        className={`py-2 px-4 rounded-lg font-medium transition-all duration-300 ${activeTab === 'journal' ? 'bg-purple-500 text-white shadow-md' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
                    >
                        <i className="fas fa-book-open mr-2"></i>Journal
                    </button>
                    <button
                        onClick={() => setActiveTab('chat')}
                        className={`py-2 px-4 rounded-lg font-medium transition-all duration-300 ${activeTab === 'chat' ? 'bg-purple-500 text-white shadow-md' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
                    >
                        <i className="fas fa-robot mr-2"></i>AI Chatbot
                    </button>
                </div>

                {/* Content Area */}
                <div className="p-6">
                    {activeTab === 'mood' && (
                        <div className="space-y-6">
                            <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-4">How are you feeling today?</h2>
                            <div className="flex flex-wrap gap-3 mb-4">
                                {['Happy', 'Neutral', 'Sad', 'Anxious', 'Energetic', 'Tired', 'Calm', 'Stressed'].map(m => (
                                    <button
                                        key={m}
                                        onClick={() => setMood(m)}
                                        className={`py-2 px-4 rounded-full text-sm font-medium transition-all duration-200
                                            ${mood === m ? 'bg-purple-500 text-white shadow-lg scale-105' : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-purple-100 dark:hover:bg-purple-900'}`}
                                    >
                                        {m}
                                    </button>
                                ))}
                            </div>
                            <button
                                onClick={handleMoodSubmit}
                                disabled={!mood}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Log Mood
                            </button>

                            <div className="mt-8">
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-3">Your Mood History</h3>
                                {moodEntries.length === 0 ? (
                                    <p className="text-gray-600 dark:text-gray-400">No mood entries yet. Log your first mood!</p>
                                ) : (
                                    <ul className="space-y-3">
                                        {moodEntries.map(entry => (
                                            <li key={entry.id} className="flex justify-between items-center bg-gray-50 dark:bg-gray-700 p-4 rounded-lg shadow-sm">
                                                <span className="font-medium text-gray-800 dark:text-gray-200">{entry.mood}</span>
                                                <span className="text-sm text-gray-500 dark:text-gray-400">{formatTimestamp(entry.timestamp)}</span>
                                                <button
                                                    onClick={() => confirmDelete(entry.id, 'mood')}
                                                    className="text-red-500 hover:text-red-700 text-lg transition-colors duration-200"
                                                    title="Delete mood entry"
                                                >
                                                    <i className="fas fa-trash"></i>
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    )}

                    {activeTab === 'journal' && (
                        <div className="space-y-6">
                            <h2 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-4">Write your thoughts</h2>
                            <textarea
                                className="w-full p-4 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 min-h-[150px]"
                                placeholder="What's on your mind today?"
                                value={journalEntry}
                                onChange={(e) => setJournalEntry(e.target.value)}
                            ></textarea>
                            <button
                                onClick={handleJournalSubmit}
                                disabled={!journalEntry.trim()}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-lg shadow-md transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Save Journal Entry
                            </button>

                            <div className="mt-8">
                                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-3">Your Journal Entries</h3>
                                {journalEntries.length === 0 ? (
                                    <p className="text-gray-600 dark:text-gray-400">No journal entries yet. Start writing!</p>
                                ) : (
                                    <ul className="space-y-3">
                                        {journalEntries.map(entry => (
                                            <li key={entry.id} className="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg shadow-sm">
                                                <p className="text-gray-800 dark:text-gray-200 mb-2">{entry.content}</p>
                                                <div className="flex justify-between items-center text-sm text-gray-500 dark:text-gray-400">
                                                    <span>{formatTimestamp(entry.timestamp)}</span>
                                                    <button
                                                        onClick={() => confirmDelete(entry.id, 'journal')}
                                                        className="text-red-500 hover:text-red-700 text-lg transition-colors duration-200"
                                                        title="Delete journal entry"
                                                    >
                                                        <i className="fas fa-trash"></i>
                                                    </button>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    )}

                    {activeTab === 'chat' && (
                        <div className="flex flex-col h-[500px] bg-gray-50 dark:bg-gray-700 rounded-lg shadow-md">
                            <div ref={chatContainerRef} className="flex-1 p-4 overflow-y-auto space-y-4">
                                {chatHistory.length === 0 ? (
                                    <div className="text-center text-gray-500 dark:text-gray-400 mt-10">
                                        Start a conversation with your AI companion!
                                    </div>
                                ) : (
                                    chatHistory.map((msg, index) => (
                                        <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                            <div className={`max-w-[70%] p-3 rounded-lg shadow-sm ${msg.role === 'user' ? 'bg-indigo-500 text-white rounded-br-none' : 'bg-gray-200 dark:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-bl-none'}`}>
                                                <p className="text-sm">{msg.text}</p>
                                                <span className="block text-xs opacity-75 mt-1">{formatTimestamp(msg.timestamp)}</span>
                                            </div>
                                        </div>
                                    ))
                                )}
                                {loadingChat && (
                                    <div className="flex justify-start">
                                        <div className="max-w-[70%] p-3 rounded-lg shadow-sm bg-gray-200 dark:bg-gray-600 text-gray-900 dark:text-gray-100 rounded-bl-none">
                                            <div className="flex items-center">
                                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-900 dark:border-gray-100 mr-2"></div>
                                                <span>Thinking...</span>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                            <form onSubmit={handleChatSubmit} className="p-4 border-t border-gray-200 dark:border-gray-600 flex items-center">
                                <input
                                    type="text"
                                    className="flex-1 p-3 border border-gray-300 dark:border-gray-600 rounded-l-lg focus:ring-indigo-500 focus:border-indigo-500 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
                                    placeholder="Type your message..."
                                    value={chatInput}
                                    onChange={(e) => setChatInput(e.target.value)}
                                    disabled={loadingChat}
                                />
                                <button
                                    type="submit"
                                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-5 rounded-r-lg shadow-md transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                                    disabled={!chatInput.trim() || loadingChat}
                                >
                                    <i className="fas fa-paper-plane"></i>
                                </button>
                            </form>
                        </div>
                    )}
                </div>
            </div>

            {/* Confirmation Modal */}
            {showConfirmation && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-xl max-w-sm w-full text-center">
                        <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-4">Confirm Deletion</h3>
                        <p className="text-gray-700 dark:text-gray-300 mb-6">Are you sure you want to delete this {deleteType} entry? This action cannot be undone.</p>
                        <div className="flex justify-center gap-4">
                            <button
                                onClick={() => setShowConfirmation(false)}
                                className="px-6 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors duration-200"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDelete}
                                className="px-6 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors duration-200"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Font Awesome for icons */}
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css"></link>
            {/* Google Fonts - Inter */}
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"></link>
        </div>
    );
};

export default App;

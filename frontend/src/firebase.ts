// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyDqEXaniP13SjvAC1fxicOQeoor04xxnmI",
  authDomain: "no-way-chat.firebaseapp.com",
  projectId: "no-way-chat",
  storageBucket: "no-way-chat.firebasestorage.app",
  messagingSenderId: "1083549262658",
  appId: "1:1083549262658:web:1541718e26d8ae67b79edb"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firestore
export const db = getFirestore(app);

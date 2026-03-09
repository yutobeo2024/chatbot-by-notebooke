
import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

// Your web app's Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyCwqq5Co57D32OGsOmLJMiR0zCiM1v2OME",
    authDomain: "yduocsaigo-407.firebaseapp.com",
    projectId: "yduocsaigo-407",
    storageBucket: "yduocsaigo-407.firebasestorage.app",
    messagingSenderId: "668579075814",
    appId: "1:668579075814:web:a5f72bfaec70982486cd27"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

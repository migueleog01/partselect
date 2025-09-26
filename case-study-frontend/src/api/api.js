
const API_BASE_URL = "http://127.0.0.1:3002";

export const getAIMessage = async (userQuery) => {
  try {
    console.log("Sending query to API Bridge:", userQuery);
    
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: userQuery
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Received response from API Bridge:", data);
    
    return {
      role: "assistant",
      content: data.content
    };
    
  } catch (error) {
    console.error("Error calling API Bridge:", error);
    
    // Return error message to user
    return {
      role: "assistant",
      content: `I'm having trouble connecting to my repair database. Please make sure the API server is running.\n\nError: ${error.message}\n\n**To start the server:**\n1. Open terminal in api-bridge folder\n2. Run: python main.py`
    };
  }
};

// Health check function
export const checkAPIHealth = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (response.ok) {
      return await response.json();
    }
    return { status: "error", error: "API not responding" };
  } catch (error) {
    return { status: "error", error: error.message };
  }
};

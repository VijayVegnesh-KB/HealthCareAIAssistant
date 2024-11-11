import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ChatbotScreen extends StatefulWidget {
  @override
  _ChatbotScreenState createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  List<Map<String, dynamic>> _messages = [];
  TextEditingController _controller = TextEditingController();
  FocusNode _focusNode = FocusNode();
  final String _apiUrl = 'http://127.0.0.1:5000/recommendation/';


  @override
  void dispose() {
    _focusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  Future<void> _sendMessageToBackend(String message) async {
    setState(() {
      _messages.add({'role': 'user', 'content': message});
    });

    try {
      final response = await http.post(
        Uri.parse(_apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'message': message}),
      );


      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        var aiResponse = data['response']['summary'] ?? 'No summary available.';
        bool hasSummary = data['response']['summary'] != null;

        if ((aiResponse is String) && hasSummary) {
          aiResponse = aiResponse.replaceAll(RegExp(r'```json|```'), '').trim();
          aiResponse = json.decode(aiResponse);

          final List medicines = aiResponse['medicines'] ?? [];
          final String note = aiResponse['disclaimer'] ?? '';

          if (medicines.isEmpty) {
            setState(() {
              _messages.add({'role': 'assistant', 'content': aiResponse['message']});
            });
          } else {
            setState(() {
              _messages.add({
                'role': 'assistant',
                'content': aiResponse['message'],
                'medicines': medicines,
                'note': note,
              });
            });
          }
        } else {
          var aiResponse = data['response'] ?? 'No response available.';
          setState(() {
            _messages.add({'role': 'assistant', 'content': aiResponse['message']});
          });
        }
      } else {
        setState(() {
          _messages.add({'role': 'assistant', 'content': 'Error: Unable to connect to backend.'});
        });
      }
    } catch (e) {
      setState(() {
        _messages.add({'role': 'assistant', 'content': 'Error: Failed to send message.'});
      });
    }
  }

  void _handleSendMessage() {
    final message = _controller.text.trim();
    if (message.isNotEmpty) {
      _controller.clear();
      _sendMessageToBackend(message);
      _focusNode.requestFocus();
    }
  }

  void _buyMedicine(Map<String, dynamic> medicine) {
    Navigator.pushNamed(
      context,
      '/checkout',
      arguments: medicine,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Chat with Health Assistant'),
        backgroundColor: Colors.blueAccent,
      ),
      body: Column(
        children: <Widget>[
          Expanded(
            child: ListView.builder(
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final message = _messages[index];

                if (message['role'] == 'assistant') {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ConstrainedBox(
                        constraints: BoxConstraints(
                          maxWidth: MediaQuery.of(context).size.width * 0.6, // Max 60% of screen width
                        ),
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 5, horizontal: 10),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.grey[300],
                            borderRadius: BorderRadius.circular(10),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withOpacity(0.1),
                                blurRadius: 4,
                                offset: Offset(2, 2),
                              ),
                            ],
                          ),
                          child: Text(
                            message['content']!,
                            style: TextStyle(color: Colors.black),
                          ),
                        ),
                      ),
                      if (message['medicines'] != null && message['medicines'].isNotEmpty)
                        ...message['medicines'].map<Widget>((medicine) {
                          return ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: MediaQuery.of(context).size.width * 0.5, // Cap width to 50% of screen width
                            ),
                            child: Card(
                              margin: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                              child: ListTile(
                                contentPadding: EdgeInsets.all(8),
                                title: Text(medicine['name']),
                                subtitle: Text("Price: \$${medicine['price']}"),
                                leading: (medicine['image'] != null && medicine['image'].isNotEmpty) ? Image.network(
                                      medicine['image']!,
                                      width: 50,
                                      height: 50,
                                      fit: BoxFit.cover,
                                    )
                                  : null,
                                trailing: ElevatedButton(
                                  onPressed: () => _buyMedicine(medicine),
                                  child: Text('Buy'),
                                ),
                              ),
                            ),
                          );
                        }).toList(),
                      if (message['note'] != null && message['note'].isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.all(8.0),
                          child: Text(
                            message['note']!,
                            style: TextStyle(color: Colors.grey[700]),
                          ),
                        ),
                    ],
                  );
                } else {
                  return Align(
                    alignment: Alignment.centerRight,
                    child: ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth: MediaQuery.of(context).size.width * 0.6, // Max 60% of screen width
                      ),
                      child: Container(
                        margin: const EdgeInsets.symmetric(vertical: 5, horizontal: 10),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.blueAccent,
                          borderRadius: BorderRadius.circular(10),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.1),
                              blurRadius: 4,
                              offset: Offset(2, 2),
                            ),
                          ],
                        ),
                        child: Text(
                          message['content']!,
                          style: TextStyle(color: Colors.white),
                        ),
                      ),
                    ),
                  );
                }
              },
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: _controller,
                    focusNode: _focusNode,
                    decoration: InputDecoration(
                      hintText: 'Describe your symptoms...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (value) {
                      _handleSendMessage();
                    },
                  ),
                ),
                IconButton(
                  icon: Icon(Icons.send),
                  onPressed: _handleSendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

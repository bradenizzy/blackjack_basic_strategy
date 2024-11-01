# index.py

from flask import Flask, render_template, request, redirect, url_for, session
import random
import os

app = Flask(__name__)
#app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key_for_dev')

# Game variables
CARD_VALUES = {
    "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10, "A": 11
}
DECK = []
CUT_CARD_POSITION = 10
RUNNING_COUNT = 0
TRUE_COUNT = 0

player_hands = []
current_hand_index = 0
dealer_hand = []
game_stats = {"correct": 0, "incorrect": 0, "wins": 0, "losses": 0, "ties": 0, "rounds_played": 0}
NUM_DECKS = 6  # Default value, but will be set in the game flow

def update_running_count(card):
    global RUNNING_COUNT, TRUE_COUNT
    if card in ["2", "3", "4", "5", "6"]:
        RUNNING_COUNT += 1
    elif card in ["10", "J", "Q", "K", "A"]:
        RUNNING_COUNT -= 1
    #TRUE_COUNT = RUNNING_COUNT * 1/len(DECK/52)???

def shuffle_deck():
    global DECK
    DECK = [card for card in CARD_VALUES.keys()] * 4 * NUM_DECKS
    random.shuffle(DECK)
    CUT_CARD_POSITION = int(0.15 * len(DECK)) + random.randint(1, int(0.05 * len(DECK)))

def enough_cards_for_round():
    return len(DECK) > CUT_CARD_POSITION

# Deal a card
def deal_card():
    return DECK.pop()

# Function to determine if the hand is soft
def is_soft(hand):
    if 'A' in hand:
        if len(hand) > 2:
            val = 0
            for card in hand:
              if card != 'A':
                val += CARD_VALUES[card]

            val += 11

            if val > 21:
                return False
            else:
                return True
        else:
            return True
    else:
      return False

# Calculate hand value
def hand_value(hand):
    value = sum(CARD_VALUES[card] for card in hand)
    aces = hand.count('A')
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    global NUM_DECKS, game_stats
    # Reset game statistics
    game_stats = {"correct":0,"incorrect":0,"wins": 0, "losses": 0, "ties": 0, "rounds_played": 0}
    
    # Get number of decks from user input
    NUM_DECKS = int(request.form.get('num_decks', 6))
    
    shuffle_deck()
    return redirect(url_for('start_round'))

@app.route('/start_round')
def start_round():
    global player_hands, dealer_hand, current_hand_index
    play_on = enough_cards_for_round()
    if not play_on:  # Not enough cards for a new round
        return redirect(url_for('end_game'))
    
    player_hands = [[deal_card(), deal_card()]]  # Initialize with one player hand
    dealer_hand = [deal_card(), deal_card()]
    current_hand_index = 0  # Start with the first hand
    return redirect(url_for('round'))

@app.route('/round')
def round():
    global current_hand_index
    player_hand_values = [hand_value(hand) for hand in player_hands]
    dealer_value = hand_value(dealer_hand[:1])  # Value of the dealer's visible card only
    feedback = request.args.get('feedback', '')

    return render_template(
        'round.html', 
        player_hands=player_hands, 
        dealer_hand=dealer_hand, 
        player_hand_values=player_hand_values, 
        dealer_value=dealer_value, 
        current_hand_index=current_hand_index,
        feedback=feedback,
        enumerate=enumerate  # Pass enumerate explicitly to the template
    )


@app.route('/action', methods=['POST'])
def action():
    global player_hands, dealer_hand, current_hand_index
    action = request.form.get('action')
    dealer_upcard_value = CARD_VALUES[dealer_hand[0]]
    player_hand = player_hands[current_hand_index]
    
    correct_action = basic_strategy(player_hand, dealer_upcard_value)
    
    # Check if the player's action matches the correct action
    if action != correct_action:
        feedback = f"Incorrect. Correct action: {correct_action}. Please try again."
        game_stats["incorrect"] += 1
        game_stats["correct"] -= 1
        # Return to the current round with feedback until user provides the correct action
        return redirect(url_for('round', feedback=feedback))

    # If the action is correct, update feedback and game stats
    feedback = "Correct!"
    game_stats["correct"] += 1

    # if action == "Surrender":
    #     if len(player_hand) == 2:
    #         # Player surrenders; dealer wins but player only loses half
    #         game_stats["losses"] += 1
    #         game_stats["rounds_played"] += 1
    #         return redirect(url_for('round_result', result='surrender', feedback=feedback))
    
    if action == "Split":
        if len(player_hand) == 2 and player_hand[0] == player_hand[1]:
            # Split into two hands
            card = player_hand[0]
            player_hands[current_hand_index] = [card, deal_card()]  # Update current hand
            player_hands.insert(current_hand_index + 1, [card, deal_card()])  # Insert new hand
            feedback += " (Hand has been split)"
        else:
            feedback = f"Invalid action: Cannot split. {feedback}"
    
    elif action == "Double":
        if len(player_hand) == 2:  # Can only double on initial hand
            player_hand.append(deal_card())
            if hand_value(player_hand) > 21:
                for card in player_hand:
                    update_running_count(card)
                for card in dealer_hand:
                    update_running_count(card)
                return redirect(url_for('round_result', result='bust', feedback=feedback, player_value=hand_value(player_hand), dealer_value=hand_value(dealer_hand)))
            # Move to dealer's turn or next hand after doubling
            return move_to_next_hand_or_dealer(feedback)
        else:
            feedback = f"Invalid action: Cannot double now. {feedback}"

    elif action == "Hit":
        player_hand.append(deal_card())
        if hand_value(player_hand) > 21:
            for card in player_hand:
                    update_running_count(card)
            for card in dealer_hand:
                update_running_count(card)
            return redirect(url_for('round_result', result='bust', feedback=feedback, player_value=hand_value(player_hand), dealer_value=hand_value(dealer_hand)))
        
    elif action == "Stand":
        return move_to_next_hand_or_dealer(feedback)
    
    return redirect(url_for('round', feedback=feedback))

def move_to_next_hand_or_dealer(feedback):
    global current_hand_index
    if current_hand_index < len(player_hands) - 1:
        # Move to the next hand
        current_hand_index += 1
        return redirect(url_for('round', feedback=feedback))
    else:
        # All hands played, move to dealer's turn
        return dealer_play(feedback)

def dealer_play(feedback):
    while hand_value(dealer_hand) < 17:
        dealer_hand.append(deal_card())
    
    # Determine results for each hand
    for hand in player_hands:
        # Update running count
        for card in hand:
            update_running_count(card)

        player_value = hand_value(hand)
        dealer_value = hand_value(dealer_hand)

        if dealer_value > 21 or player_value > dealer_value:
            result = 'win'
            game_stats["wins"] += 1
        elif dealer_value == player_value:
            result = 'push'
            game_stats["ties"] += 1
        else:
            result = 'lose'
            game_stats["losses"] += 1

        game_stats["rounds_played"] += 1

    for card in dealer_hand:
        update_running_count(card)

    return redirect(url_for('round_result', result=result, feedback=feedback, player_value=player_value, dealer_value=dealer_value))

@app.route('/round_result')
def round_result():
    global RUNNING_COUNT
    result = request.args.get('result')
    feedback = request.args.get('feedback', '')
    dealer_value = request.args.get('dealer_value', type=int)

    # Calculate player hand values for each hand in player_hands
    player_hand_values = [hand_value(hand) for hand in player_hands]

    return render_template(
        'round_result.html', 
        result=result, 
        player_hands=player_hands, 
        dealer_hand=dealer_hand, 
        feedback=feedback,
        player_hand_values=player_hand_values,
        dealer_value=dealer_value,
        count=RUNNING_COUNT,
        enumerate=enumerate  # Pass enumerate explicitly to the template
    )


@app.route('/end_game')
def end_game():
    return render_template('end_game.html', game_stats=game_stats)

# Function to apply basic strategy
def basic_strategy(player_hand, dealer_value):
    player_value = hand_value(player_hand)
    
    bool_soft = is_soft(player_hand)
    
    # # Check for surrender
    # if not bool_soft and player_value == 16 and dealer_value in [9, 10, 11] and len(player_hand) == 2:
    #     return "Surrender"
    # elif not bool_soft and player_value == 15 and dealer_value == 10 and len(player_hand) == 2:
    #     return "Surrender"
    
    # Check for pairs (splitting)
    if len(player_hand) == 2 and player_hand[0] == player_hand[1]:
        pair_card = player_hand[0]
        if pair_card == 'A':
            return "Split"
        elif pair_card in ['10', 'J', 'Q', 'K']:
            return "Stand"
        elif pair_card == '9' and dealer_value in [2, 3, 4, 5, 6, 8, 9]:
            return "Split"
        elif pair_card == '8':
            return "Split"
        elif pair_card == '7' and dealer_value in [2, 3, 4, 5, 6, 7]:
            return "Split"
        elif pair_card == '6' and dealer_value in [2, 3, 4, 5, 6]:
            return "Split"
        elif pair_card == '5' and dealer_value in [2, 3, 4, 5, 6, 7, 8, 9]:
            return "Double"
        elif pair_card == '4' and dealer_value in [5, 6]:
            return "Split"
        elif pair_card == '3' and dealer_value in [2, 3, 4, 5, 6, 7]:
            return "Split"
        elif pair_card == '2' and dealer_value in [2, 3, 4, 5, 6, 7]:
            return "Split"
    
    # Check for soft totals
    if bool_soft:
        if player_value == 20:
            return "Stand"
        elif player_value == 19 and dealer_value == 6:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 19:
            return "Stand"
        elif player_value == 18 and dealer_value in [2, 3, 4, 5, 6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 18 and dealer_value in [9, 10, 11]:
            return "Hit"
        elif player_value == 18:
            return "Stand"
        elif player_value == 17 and dealer_value in [3, 4, 5, 6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 17:
            return "Hit"
        elif player_value == 16 and dealer_value in [4,5,6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 16:
            return "Hit"
        elif player_value == 15 and dealer_value in [4,5,6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 15:
            return "Hit"
        elif player_value == 14 and dealer_value in [5,6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 14:
            return "Hit"
        elif player_value == 13 and dealer_value in [5,6]:
            if len(player_hand) == 2:
                return "Double"
            else:
                return "Hit"
        elif player_value == 13:
            return "Hit"

    # Check for hard totals
    if player_value >= 17:
        return "Stand"
    elif player_value == 16 and dealer_value in [2, 3, 4, 5, 6]:
        return "Stand"
    elif player_value == 16:
        return "Hit"
    elif player_value == 15 and dealer_value in [2, 3, 4, 5, 6]:
        return "Stand"
    elif player_value == 15:
        return "Hit"
    elif player_value == 14 and dealer_value in [2, 3, 4, 5, 6]:
        return "Stand"
    elif player_value == 14:
        return "Hit"
    elif player_value == 13 and dealer_value in [2, 3, 4, 5, 6]:
        return "Stand"
    elif player_value == 13:
        return "Hit"
    elif player_value == 12 and dealer_value in [4, 5, 6]:
        return "Stand"
    elif player_value == 12:
        return "Hit"
    elif player_value == 11:
        if len(player_hand) == 2:
            return "Double"
        else:
            return "Hit"
    elif player_value == 10 and dealer_value in [2, 3, 4, 5, 6, 7, 8, 9]:
        if len(player_hand) == 2:
            return "Double"
        else:
            return "Hit"
    elif player_value == 10:
        return "Hit"
    elif player_value == 9 and dealer_value in [3, 4, 5, 6]:
        if len(player_hand) == 2:
            return "Double"
        else:
            return "Hit"
    elif player_value == 9:
        return "Hit"
    else:
        return "Hit"

if __name__ == "__main__":
    app.run()

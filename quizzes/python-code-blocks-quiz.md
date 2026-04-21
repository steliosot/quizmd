# Python Code Blocks Quiz

## Question 1
What is the time complexity of this code?

```python
for item in items:
    print(item)
```

- O(1)
- O(log n)
- O(n)
- O(n^2)

Answer: 3
Type: single
Time: 30
Explanation: The loop runs once per item, so it is linear time.

## Question 2
What does this function return for `nums=[1, 2, 3]`?

```python
def f(nums):
    total = 0
    for n in nums:
        total += n
    return total
```

- 5
- 6
- 7
- [1, 2, 3]

Answer: 2
Type: single
Time: 30
Explanation: It sums all values: 1 + 2 + 3 = 6.

## Question 3
Which statements are true about this code?

```python
values = [2, 4, 6]
result = [v // 2 for v in values]
```

- `result` becomes `[1, 2, 3]`
- `//` performs floor division
- `values` is modified in place
- This is a list comprehension

Answer: 1,2,4
Type: multiple
Time: 40
Explanation: The comprehension creates a new list with floor-divided values; original list is unchanged.

## Question 4
What is printed by this code?

```python
x = 3
if x > 5:
    print("A")
else:
    print("B")
```

- A
- B
- Nothing
- Error

Answer: 2
Type: single
Time: 25
Explanation: Since 3 is not greater than 5, the `else` branch prints B.

## Question 5
Which are correct ways to iterate with index and value in Python?

```python
items = ["a", "b", "c"]
```

- `for i, v in enumerate(items):`
- `for i in range(len(items)):` then access `items[i]`
- `for i, v in items:`
- `for v in items:`

Answer: 1,2,4
Type: multiple
Time: 40
Explanation: `enumerate`, index-based iteration, and value-only iteration are valid. `for i, v in items` is invalid for plain strings.

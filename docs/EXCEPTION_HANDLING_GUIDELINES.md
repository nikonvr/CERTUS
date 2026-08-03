# CERTUS - Directives pour le traitement des exceptions (Exception Handling Guidelines)

Ce document résume les bonnes pratiques à respecter lors de la manipulation des exceptions au sein de l'application CERTUS, afin d'éviter la dette technique, de faciliter le débogage et de fiabiliser le système de reporting d'erreurs.

---

## 1. Bannir les clauses `except:` vides (Bare Excepts)

L'utilisation de `except:` sans type d'exception intercepte absolument toutes les erreurs, y compris les interruptions système importantes comme `SystemExit`, `KeyboardInterrupt` ou les erreurs de mémoire comme `MemoryError`.

* **À éviter :**
  ```python
  try:
      traitement()
  except:
      pass
  ```
* **Recommandé :** Spécifier au minimum `Exception` si l'on souhaite attraper toutes les erreurs applicatives standard :
  ```python
  try:
      traitement()
  except Exception as e:
      logging.error("Échec de traitement: %s", e)
  ```

---

## 2. Éviter d'étouffer les exceptions (Silent Passes)

Lancer un `pass` silencieux empêche d'identifier la racine d'un bug en phase de production. Toute exception interceptée qui n'est pas réémise doit être documentée et logguée à un niveau approprié (`debug`, `warning` ou `error`).

* **À éviter :**
  ```python
  try:
      charger_config()
  except OSError:
      pass
  ```
* **Recommandé :**
  ```python
  try:
      charger_config()
  except OSError as e:
      logging.warning("Impossible de charger la configuration, utilisation des valeurs par défaut: %s", e)
  ```
* **Exception autorisée :** Si le comportement silencieux est requis de manière légitime et nominale, documentez-le explicitement dans le code avec un commentaire `# Explication`.

---

## 3. Préférer les exceptions spécifiques aux génériques

Il faut capturer uniquement les types d'erreurs que le bloc est conçu pour gérer. Par exemple, si l'on attend une erreur de type clé absente dans un dictionnaire, intercepter `KeyError` plutôt que `Exception`.

* **Exemple :**
  ```python
  try:
      valeur = data["cle"]
  except KeyError:
      valeur = DEFAULT_VAL
  ```

---

## 4. Préserver la trace de la pile (Stack Trace)

Lors du traitement d'erreurs critiques, il est crucial de conserver l'historique de l'erreur dans les logs avec le paramètre `exc_info=True` ou en utilisant `logging.exception`.

* **Recommandé :**
  ```python
  try:
      operation_complexe()
  except Exception:
      logging.exception("L'opération complexe a échoué")
  ```
